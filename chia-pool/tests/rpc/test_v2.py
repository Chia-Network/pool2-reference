from __future__ import annotations

from unittest.mock import PropertyMock, patch

import aiohttp
import pytest
from api.service import Service as ServiceAPI
from chia._tests.environments.wallet import WalletTestFramework
from chia.protocols import pool_protocol
from chia.util.keychain import mnemonic_to_seed
from chia_rs import G2Element, PrivateKey
from chia_rs.chia_rs import AugSchemeMPL
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16, uint64

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
@pytest.mark.standard_block_tools
@pytest.mark.anyio
async def test_v2_rpc(
    wallet_envs: WalletTestFramework, reference_service: tuple[ServiceAPI, PropertyMock], farmer_rpc_url: str
) -> None:
    service, current_time = reference_service
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{farmer_rpc_url}/v2/get_pool_info",
            json={},
            ssl=False,
        ) as resp:
            pool_protocol.GetPoolInfoResponse.from_json_dict(
                await resp.json()
            )  # checking that this is a success response
        async with session.post(
            f"{farmer_rpc_url}/v2/post_farmer",
            json=pool_protocol.PostFarmerRequest(
                payload=pool_protocol.PostFarmerPayload(
                    launcher_id=bytes32.zeros,
                    authentication_token=uint64(0),
                    authentication_public_key=SK.get_g1(),
                    payout_instructions=wallet_address,
                    suggested_difficulty=uint64(0),
                    authentication_token_v2="",
                ),
                signature=G2Element(),  # TODO
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            pool_protocol.PostFarmerResponse.from_json_dict(
                await resp.json()
            )  # checking that this is a success response
        async with session.get(
            f"{farmer_rpc_url}/v2/get_auth",
            json=pool_protocol.GetAuthRequest(
                pool_protocol.AuthenticationPayloadV2(
                    launcher_id=bytes32.zeros,
                    timestamp=current_time.return_value,
                ),
                signature=AugSchemeMPL.sign(
                    SK,
                    bytes(uint64(current_time.return_value))
                    + bytes32.zeros
                    + bytes(service.config["pool_identity"]["pool_claim_hash"], "utf8"),
                ),
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            login_response = pool_protocol.GetAuthResponse.from_json_dict(await resp.json())
        async with session.put(
            f"{farmer_rpc_url}/v2/put_farmer",
            json=pool_protocol.PutFarmerRequest(
                payload=pool_protocol.PutFarmerPayload(
                    launcher_id=bytes32.zeros,
                    payout_instructions=wallet_address2,
                    suggested_difficulty=uint64(10),
                    authentication_token=uint64(0),
                    authentication_public_key=SK.get_g1(),
                    authentication_token_v2=login_response.authentication_token,
                ),
                signature=G2Element(),  # TODO
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            pool_protocol.PutFarmerResponse.from_json_dict(await resp.json())
        async with session.get(
            f"{farmer_rpc_url}/v2/get_farmer",
            json=pool_protocol.GetFarmerRequest(
                launcher_id=bytes32.zeros,
                authentication_token=uint64(0),
                authentication_token_v2=login_response.authentication_token,
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            farmer_response = pool_protocol.GetFarmerResponse.from_json_dict(await resp.json())
            assert farmer_response == pool_protocol.GetFarmerResponse(
                authentication_public_key=SK.get_g1(),
                payout_instructions=wallet_address2,
                current_difficulty=uint64(10),
                current_points=uint64(0),
            )
        recent_eos_hashes = wallet_envs.full_node.full_node.full_node_store.recent_eos.cache.keys()
        recent_sp_hashes = wallet_envs.full_node.full_node.full_node_store.recent_signage_points.cache.keys()
        use_eos_hash = len(list(recent_eos_hashes)) != 0
        partial = pool_protocol.PostPartialPayload(
            launcher_id=bytes32.zeros,
            authentication_token=uint64(0),
            proof_of_space=(await wallet_envs.full_node.get_all_full_blocks())[-1].reward_chain_block.proof_of_space,
            sp_hash=next(iter(recent_eos_hashes if use_eos_hash else recent_sp_hashes)),
            end_of_sub_slot=use_eos_hash,
            harvester_id=bytes32.zeros,
        )
        original_difficulty = (await service.store.get_farmer(launcher_id=bytes32.zeros))["difficulty"]
        with (
            patch("farmer_rpc.v2.AugSchemeMPL.aggregate_verify", return_value=True),
            patch("farmer_rpc.v2.RewardPuzzle.puzzle_hash", return_value=None),
            patch("farmer_rpc.v2.verify_and_get_quality_string", return_value=bytes32.zeros),
            patch("farmer_rpc.v2.calculate_iterations_quality", return_value=uint64(10)),
        ):
            for _ in range(3):
                async with session.post(
                    f"{farmer_rpc_url}/v2/post_partial",
                    json=pool_protocol.PostPartialRequest(
                        payload=partial,
                        authentication_token_v2=login_response.authentication_token,
                        aggregate_signature=G2Element(),
                    ).to_json_dict(),
                    ssl=False,
                ) as resp:
                    pool_protocol.PostPartialResponse.from_json_dict(await resp.json())
                await service.store.confirm_partials(launcher_id=bytes32.zeros, until_timestamp=service.current_time)
                current_time.return_value += 1

        assert (await service.store.get_farmer(launcher_id=bytes32.zeros))["difficulty"] > original_difficulty

        # Test authentication token expiration
        current_time.return_value += 60
        async with session.get(
            f"{farmer_rpc_url}/v2/get_farmer",
            json=pool_protocol.GetFarmerRequest(
                launcher_id=bytes32.zeros,
                authentication_token=uint64(0),
                authentication_token_v2=login_response.authentication_token,
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            error_response = pool_protocol.ErrorResponse.from_json_dict(await resp.json())
            assert error_response == pool_protocol.ErrorResponse(
                error_code=uint16(pool_protocol.PoolErrorCode.INVALID_AUTHENTICATION_TOKEN.value),
                error_message=f"Invalid authentication token for launcher_id {bytes32.zeros.hex()}.",
            )
