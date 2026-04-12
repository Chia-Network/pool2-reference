from __future__ import annotations

import pathlib
import unittest
from collections.abc import AsyncIterator
from unittest.mock import PropertyMock, patch

import aiohttp
import pytest
import yaml
from api.service import Service as ServiceAPI
from chia._tests.conftest import (  # noqa: PLC2701
    blockchain_constants,  # noqa: F401
    consensus_mode,  # noqa: F401
    farmer_harvester_2_simulators_zero_bits_plot_filter,  # noqa: F401
    self_hostname,  # noqa: F401
    trusted_full_node,  # noqa: F401
    tx_config,  # noqa: F401
)
from chia._tests.environments.wallet import WalletTestFramework
from chia._tests.wallet.conftest import wallet_environments  # noqa: PLC2701, F401
from chia.protocols import pool_protocol
from chia.util.keychain import mnemonic_to_seed
from chia_rs import G2Element, PrivateKey
from chia_rs.chia_rs import AugSchemeMPL
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16, uint64
from click.testing import CliRunner
from farmer_rpc.v2 import HANDLERS, METADATA
from node.config import CONFIG_FILE_NAME as NODE_CONFIG_FILE
from node.rpc_wrapper import NodeRPC
from server.config import CONFIG_FILE_NAME as SERVER_CONFIG_FILE
from server.farmer_rpc import FarmerRPCServer
from service.config import CONFIG_FILE_NAME as SERVICE_CONFIG_FILE
from service.service import Service
from store.config import CONFIG_FILE_NAME as STORE_CONFIG_FILE
from store.sqlite import Store as SqliteStore
from tests.server.test_server import _generate_ssl_cert  # noqa: PLC2701
from wallet.config import CONFIG_FILE_NAME as WALLET_CONFIG_FILE
from wallet.rpc_wrapper import WalletRPC


@pytest.fixture
async def environments(
    self_hostname: str,  # noqa: F811
    wallet_environments: WalletTestFramework,  # noqa: F811
    tmp_path: pathlib.Path,
) -> AsyncIterator[tuple[WalletTestFramework, ServiceAPI, PropertyMock, str]]:
    env = wallet_environments.environments[0]
    ssl_cert_path, ssl_key_path = _generate_ssl_cert(tmp_path)
    runner = CliRunner()
    with runner.isolated_filesystem():
        server_config_path = pathlib.Path.cwd().joinpath(SERVER_CONFIG_FILE)
        service_config_path = pathlib.Path.cwd().joinpath(SERVICE_CONFIG_FILE)
        node_config_path = pathlib.Path.cwd().joinpath(NODE_CONFIG_FILE)
        wallet_config_path = pathlib.Path.cwd().joinpath(WALLET_CONFIG_FILE)
        store_config_path = pathlib.Path.cwd().joinpath(STORE_CONFIG_FILE)
        try:
            store_config_path.touch()
            service_config_path.touch()
            node_config_path.touch()
            wallet_config_path.touch()
            server_config_path.touch()
            with server_config_path.open(mode="w") as file:
                TODO = 0
                yaml.dump(
                    {
                        "logging": {
                            "log_level": "DEBUG",
                            "log_stdout": True,
                            "log_syslog": False,
                            "log_syslog_host": "",
                            "log_syslog_port": TODO,
                            "log_filename": "",
                            "log_maxfilesrotation": TODO,
                            "log_max_bytes_rotation": TODO,
                            "log_use_gzip": True,
                        },
                        "pool_info": {
                            "name": "",
                            "logo_url": "https://foo.com",
                            "description": "",
                            "welcome_message": "",
                            "minimum_difficulty": TODO,
                        },
                        "web_config": {
                            "host": "localhost",
                            "port": 0,
                            "ssl_cert_path": str(ssl_cert_path),
                            "ssl_key_path": str(ssl_key_path),
                        },
                        "service_loop_intervals": 1,
                        "authentication_token_timeout": 1,
                    },
                    file,
                )
            with store_config_path.open(mode="w") as file:
                yaml.dump({"store_path": str(tmp_path.joinpath("store.sqlite"))}, file)
            with node_config_path.open(mode="w") as file:
                yaml.dump(
                    {
                        "self_hostname": self_hostname,
                        "rpc_port": wallet_environments.full_node_rpc_client.port,
                        "root_path": str(env.node.root_path),
                        "net_config": {
                            "rpc_timeout": env.service.config["rpc_timeout"],
                            "daemon_ssl": env.service.config["daemon_ssl"],
                            "private_ssl_ca": env.service.config["private_ssl_ca"],
                        },
                    },
                    file,
                )
            with wallet_config_path.open(mode="w") as file:
                yaml.dump(
                    {
                        "self_hostname": self_hostname,
                        "rpc_port": env.rpc_server.listen_port,
                        "root_path": str(env.node.root_path),
                        "net_config": {
                            "rpc_timeout": env.service.config["rpc_timeout"],
                            "daemon_ssl": env.service.config["daemon_ssl"],
                            "private_ssl_ca": env.service.config["private_ssl_ca"],
                        },
                    },
                    file,
                )
            async with env.wallet_state_manager.new_action_scope(
                tx_config=wallet_environments.tx_config, push=True
            ) as action_scope:
                puzzle_hash = await action_scope.get_puzzle_hash(env.wallet_state_manager)
            with service_config_path.open(mode="w") as file:
                TODO = 0
                yaml.dump(
                    {
                        "pool_identity": {
                            "relative_lock_height": 5,
                            "pool_claim_hash": puzzle_hash.hex(),
                            "pool_memoization": "80",
                        },
                        "min_difficulty": 0,
                        "default_difficulty": TODO,
                        "partial_time_limit": TODO,
                        "partial_confirmation_delay": 600,  # 10 minutes
                        "scan_start_height": TODO,
                        "collect_pool_rewards_interval": TODO,
                        "confirmation_security_threshold": TODO,
                        "payment_interval": TODO,
                        "max_additions_per_transaction": TODO,
                        "number_of_partials_target": 2,
                        "time_target": 2,
                        "fee_basis_points": 1000,  # 10%
                        "genesis_challenge": env.node.constants.GENESIS_CHALLENGE.hex(),
                    },
                    file,
                )
            async with NodeRPC.create() as node_rpc, WalletRPC.create() as wallet_rpc, SqliteStore.create() as store:
                # mock in a timestamp
                with patch.object(Service, "current_time", new_callable=PropertyMock) as current_time:
                    service = Service.create(store=store, full_node=node_rpc, wallet=wallet_rpc)
                    current_time.return_value = uint64(service.config["partial_confirmation_delay"] + 3600)
                    async with FarmerRPCServer.create_rpc(
                        farmer_rpcs={"v2": METADATA},
                        handlers={"v2": HANDLERS},
                        service=service,
                        token_sk=bytes32.zeros,
                    ) as farmer_rpc:
                        port = farmer_rpc.site._server.sockets[0].getsockname()[1]
                        yield wallet_environments, service, current_time, f"https://localhost:{port}"
        finally:
            if store_config_path.exists():
                wallet_config_path.unlink()
            if node_config_path.exists():
                node_config_path.unlink()
            if service_config_path.exists():
                service_config_path.unlink()
            if wallet_config_path.exists():
                wallet_config_path.unlink()
            if server_config_path.exists():
                server_config_path.unlink()


SK = PrivateKey.from_seed(
    seed=mnemonic_to_seed(
        "cluster deal notable hello grace strong grace army skirt magnet million tool outer "
        "parade shed pony riot sign evoke awake spatial quote shoot ribbon"
    )
)
wallet_address = "xch1skwfr5zdt8l850fzc6984hlr74fcw93mlnzzmkdhr6dmr9vxpk3sl0fvzg"
wallet_address2 = "xch1ne8gwkm975x3sm48j99gr686g0v9nsdj9j9suxu929za756k272q34kfd6"
POOL_SK = PrivateKey.from_seed(
    seed=mnemonic_to_seed(
        "cluster deal notable hello grace strong grace army skirt magnet million tool outer "
        "parade shed pony riot sign evoke awake spatial quote shoot bacon"
    )
)
PLOT_SK = PrivateKey.from_seed(
    seed=mnemonic_to_seed(
        "cluster deal notable hello grace strong grace army skirt magnet million tool outer "
        "parade shed pony riot sign evoke awake spatial quote bacon bacon"
    )
)


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [1]}],
    indirect=True,
)
@pytest.mark.standard_block_tools
@pytest.mark.anyio
async def test_v2_rpc(environments: tuple[WalletTestFramework, ServiceAPI, PropertyMock, str]) -> None:
    test_framework, service, current_time, base_url = environments
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{base_url}/v2/get_pool_info",
            json={},
            ssl=False,
        ) as resp:
            pool_protocol.GetPoolInfoResponse.from_json_dict(
                await resp.json()
            )  # checking that this is a success response
        async with session.post(
            f"{base_url}/v2/post_farmer",
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
            f"{base_url}/v2/get_auth",
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
            f"{base_url}/v2/put_farmer",
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
            f"{base_url}/v2/get_farmer",
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
        recent_eos_hashes = test_framework.full_node.full_node.full_node_store.recent_eos.cache.keys()
        recent_sp_hashes = test_framework.full_node.full_node.full_node_store.recent_signage_points.cache.keys()
        use_eos_hash = len(list(recent_eos_hashes)) != 0
        partial = pool_protocol.PostPartialPayload(
            launcher_id=bytes32.zeros,
            authentication_token=uint64(0),
            proof_of_space=(await test_framework.full_node.get_all_full_blocks())[-1].reward_chain_block.proof_of_space,
            sp_hash=next(iter(recent_eos_hashes if use_eos_hash else recent_sp_hashes)),
            end_of_sub_slot=use_eos_hash,
            harvester_id=bytes32.zeros,
        )
        original_difficulty = (await service.store.get_farmer(launcher_id=bytes32.zeros))["difficulty"]
        with (
            unittest.mock.patch("farmer_rpc.v2.AugSchemeMPL.aggregate_verify", return_value=True),
            unittest.mock.patch("farmer_rpc.v2.RewardPuzzle.puzzle_hash", return_value=None),
            unittest.mock.patch("farmer_rpc.v2.verify_and_get_quality_string", return_value=bytes32.zeros),
            unittest.mock.patch("farmer_rpc.v2.calculate_iterations_quality", return_value=uint64(10)),
        ):
            for _ in range(3):
                async with session.post(
                    f"{base_url}/v2/post_partial",
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
            f"{base_url}/v2/get_farmer",
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
