from __future__ import annotations

import dataclasses
import pathlib
from unittest.mock import AsyncMock, PropertyMock, patch

import farmer_rpc.v2
import pytest
from api.node_rpc import GetRecentSignagePointOrEOSResponse
from api.server import CONFIG_FILE_NAME, Config, FarmerRPCError
from api.service import Service as ServiceAPI
from chia._tests.environments.wallet import WalletTestFramework
from chia.pools.plotnft_drivers import RewardPuzzle
from chia.protocols import pool_protocol
from chia.util.keychain import mnemonic_to_seed
from chia_rs import G2Element, PrivateKey
from chia_rs.chia_rs import AugSchemeMPL
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64
from config_loading import canonical_load_config
from server.config import ConfigSchema

SK = PrivateKey.from_seed(
    seed=mnemonic_to_seed(
        "cluster deal notable hello grace strong grace army skirt magnet million tool outer "
        "parade shed pony riot sign evoke awake spatial quote shoot ribbon"
    )
)
wallet_address = "xch1skwfr5zdt8l850fzc6984hlr74fcw93mlnzzmkdhr6dmr9vxpk3sl0fvzg"
wallet_address2 = "xch1ne8gwkm975x3sm48j99gr686g0v9nsdj9j9suxu929za756k272q34kfd6"


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [1]}],
    indirect=True,
)
@pytest.mark.anyio
async def test_v2_rpc(
    wallet_envs: WalletTestFramework,
    reference_service: tuple[ServiceAPI, PropertyMock],
    server_config: None,
    root_path: pathlib.Path,
) -> None:
    service, current_time = reference_service
    config = canonical_load_config(
        root_path=root_path, config_filename=CONFIG_FILE_NAME, schema_validation=ConfigSchema(), config_type=Config
    )
    pool_info_response = await farmer_rpc.v2.get_pool_info(
        None,
        service,
        config,
        bytes32.zeros,
    )
    assert isinstance(pool_info_response, pool_protocol.GetPoolInfoResponse)
    post_farmer_response = await farmer_rpc.v2.post_farmer(
        pool_protocol.PostFarmerRequest(
            payload=pool_protocol.PostFarmerPayload(
                launcher_id=bytes32.zeros,
                authentication_token=uint64(0),
                authentication_public_key=SK.get_g1(),
                payout_instructions=wallet_address,
                suggested_difficulty=uint64(0),
            ),
            signature=G2Element(),  # TODO
        ),
        service,
        config,
        bytes32.zeros,
    )
    assert isinstance(post_farmer_response, pool_protocol.PostFarmerResponse)
    login_response = await farmer_rpc.v2.get_auth(
        pool_protocol.GetAuthRequest(
            launcher_id=bytes32.zeros,
            timestamp=current_time.return_value,
            signature=AugSchemeMPL.sign(
                SK,
                bytes(uint64(current_time.return_value))
                + bytes32.zeros
                + bytes32.from_hexstr(service.config["pool_identity"]["pool_claim_hash"]),
            ),
        ),
        service,
        config,
        bytes32.zeros,
    )
    put_farmer_response = await farmer_rpc.v2.put_farmer(
        pool_protocol.PutFarmerRequest(
            payload=pool_protocol.PutFarmerPayload(
                launcher_id=bytes32.zeros,
                payout_instructions=wallet_address2,
                suggested_difficulty=uint64(10),
                authentication_token=uint64(0),
                authentication_public_key=SK.get_g1(),
                authentication_token_v2=login_response.authentication_token,
            ),
            signature=G2Element(),  # TODO
        ),
        service,
        config,
        bytes32.zeros,
    )
    assert isinstance(put_farmer_response, pool_protocol.PutFarmerResponse)
    get_farmer_response = await farmer_rpc.v2.get_farmer(
        pool_protocol.GetFarmerRequest(
            launcher_id=bytes32.zeros,
            authentication_token=uint64(0),
            authentication_token_v2=login_response.authentication_token,
        ),
        service,
        config,
        bytes32.zeros,
    )
    assert get_farmer_response == pool_protocol.GetFarmerResponse(
        authentication_public_key=SK.get_g1(),
        payout_instructions=wallet_address2,
        current_difficulty=uint64(10),
        current_points=uint64(0),
    )
    pos = (await wallet_envs.full_node.get_all_full_blocks())[-1].reward_chain_block.proof_of_space
    pos = pos.replace(pool_contract_puzzle_hash=RewardPuzzle(singleton_id=bytes32.zeros).puzzle_hash())
    partial = pool_protocol.PostPartialPayload(
        launcher_id=bytes32.zeros,
        authentication_token=uint64(0),
        proof_of_space=pos,
        sp_hash=bytes32.zeros,
        end_of_sub_slot=True,
        harvester_id=bytes32.zeros,
    )
    original_difficulty = (await service.store.get_farmer(launcher_id=bytes32.zeros))["difficulty"]
    with (
        patch("farmer_rpc.v2.AugSchemeMPL.aggregate_verify", return_value=True),
        patch("farmer_rpc.v2.verify_and_get_quality_string", return_value=bytes32.zeros),
        patch("farmer_rpc.v2.calculate_iterations_quality", return_value=uint64(10)),
        patch.object(
            service.full_node,
            "get_recent_end_of_subslot",
            new=AsyncMock(
                return_value=GetRecentSignagePointOrEOSResponse(
                    eos=PropertyMock(),
                    signage_point=None,
                    time_received=service.current_time,
                    exists=True,
                    reverted=False,
                )
            ),
        ),
    ):
        for i in range(3):
            partial = dataclasses.replace(  # we gotta shake up the POS a bit so the partials aren't deduped in the DB
                partial, proof_of_space=partial.proof_of_space.replace(challenge=bytes32([i] * 32))
            )
            partial_response = await farmer_rpc.v2.post_partial(
                pool_protocol.PostPartialRequest(
                    payload=partial,
                    authentication_token_v2=login_response.authentication_token,
                    aggregate_signature=G2Element(),
                ),
                service,
                config,
                bytes32.zeros,
            )
            assert isinstance(partial_response, pool_protocol.PostPartialResponse)
            await service.store.confirm_partials(
                launcher_id=bytes32.zeros, until_timestamp=uint64(service.current_time + 1)
            )
            current_time.return_value += 1

    assert (await service.store.get_farmer(launcher_id=bytes32.zeros))["difficulty"] > original_difficulty

    # Test authentication token expiration
    current_time.return_value += 60
    with pytest.raises(FarmerRPCError):
        await farmer_rpc.v2.get_farmer(
            pool_protocol.GetFarmerRequest(
                launcher_id=bytes32.zeros,
                authentication_token=uint64(0),
                authentication_token_v2=login_response.authentication_token,
            ),
            service,
            config,
            bytes32.zeros,
        )
