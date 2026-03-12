from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from unittest.mock import PropertyMock, patch

import aiohttp
import pytest
import yaml
from api.farmer_protocols.rest import ErrorResponse, PoolErrorCode
from api.farmer_protocols.v2.farmer import (
    FarmerPayload,
    FarmerRequest,
    GetFarmerRequest,
    GetFarmerResponse,
    GetLoginRequest,
    GetLoginResponse,
    GetPoolInfoResponse,
    PartialPayload,
    PostFarmerResponse,
    PostPartialRequest,
    PostPartialResponse,
    PutFarmerResponse,
)
from api.service import Service as ServiceAPI
from chia._tests.conftest import (
    blockchain_constants,  # noqa: PLC2701, F401
    consensus_mode,  # noqa: PLC2701, F401
    farmer_harvester_2_simulators_zero_bits_plot_filter,  # noqa: PLC2701, F401
    self_hostname,  # noqa: PLC2701, F401
    trusted_full_node,  # noqa: PLC2701, F401
    tx_config,  # noqa: PLC2701, F401
)
from chia._tests.environments.wallet import WalletTestFramework
from chia._tests.wallet.conftest import wallet_environments  # noqa: PLC2701, F401
from chia.util.keychain import mnemonic_to_seed
from chia_rs import G2Element, PrivateKey, ProofOfSpace
from chia_rs.chia_rs import AugSchemeMPL
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint16, uint64
from farmer_rpc.v2 import HANDLERS, METADATA
from node.config import CONFIG_FILE_NAME as NODE_CONFIG_FILE
from node.rpc_wrapper import NodeRPC
from server.config import CONFIG_FILE_NAME as SERVER_CONFIG_FILE
from server.farmer_rpc import FarmerRPCServer
from service.config import CONFIG_FILE_NAME as SERVICE_CONFIG_FILE
from service.service import Service
from store.config import CONFIG_FILE_NAME as STORE_CONFIG_FILE
from store.sqlite import Store as SqliteStore
from wallet.config import CONFIG_FILE_NAME as WALLET_CONFIG_FILE
from wallet.rpc_wrapper import WalletRPC


@pytest.fixture
async def environments(
    self_hostname: str,  # noqa: F811
    wallet_environments: WalletTestFramework,  # noqa: F811
    tmp_path: pathlib.Path,
) -> AsyncIterator[tuple[WalletTestFramework, ServiceAPI, PropertyMock]]:
    env = wallet_environments.environments[0]
    server_config_path = pathlib.Path.home().joinpath(SERVER_CONFIG_FILE)
    service_config_path = pathlib.Path.home().joinpath(SERVICE_CONFIG_FILE)
    node_config_path = pathlib.Path.home().joinpath(NODE_CONFIG_FILE)
    wallet_config_path = pathlib.Path.home().joinpath(WALLET_CONFIG_FILE)
    store_config_path = pathlib.Path.home().joinpath(STORE_CONFIG_FILE)
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
                        "log_syslog": True,
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
                        "port": 8080,
                        # TODO: don't rely on chia config here
                        "ssl_cert_path": str(
                            pathlib.Path.home().joinpath(".chia/mainnet/config/ssl/ca/private_ca.crt")
                        ),
                        "ssl_key_path": str(pathlib.Path.home().joinpath(".chia/mainnet/config/ssl/ca/private_ca.key")),
                    },
                    "service_loop_intervals": 1,
                    "authentication_token_timeout": 0,
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
                    "number_of_partials_target": TODO,
                    "time_target": TODO,
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
                ):
                    yield wallet_environments, service, current_time
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


@pytest.mark.parametrize(
    "wallet_environments",
    [{"num_environments": 1, "blocks_needed": [1]}],
    indirect=True,
)
@pytest.mark.anyio
async def test_service(environments: tuple[WalletTestFramework, ServiceAPI, PropertyMock]) -> None:
    _, service, current_time = environments
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://localhost:8080/v2/get_pool_info",
            json={},
            ssl=False,
        ) as resp:
            GetPoolInfoResponse.from_json_dict(await resp.json())  # checking that this is a success response
        async with session.post(
            "https://localhost:8080/v2/post_farmer",
            json=FarmerRequest(
                payload=FarmerPayload(
                    launcher_id=bytes32.zeros,
                    authentication_public_key=SK.get_g1(),
                    payout_instructions=wallet_address,
                    suggested_difficulty=uint64(0),
                ),
                signature=G2Element(),  # TODO
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            PostFarmerResponse.from_json_dict(await resp.json())  # checking that this is a success response
        async with session.get(
            "https://localhost:8080/v2/get_login",
            json=GetLoginRequest(
                launcher_id=bytes32.zeros,
                timestamp=current_time.return_value,
                signature=AugSchemeMPL.sign(
                    SK,
                    bytes(uint64(current_time.return_value))
                    + bytes32.zeros
                    + bytes(service.config["pool_identity"]["pool_claim_hash"], "utf8"),
                ),
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            login_response = GetLoginResponse.from_json_dict(await resp.json())
            assert login_response.recent_partials == []
        async with session.put(
            "https://localhost:8080/v2/put_farmer",
            json=FarmerRequest(
                payload=FarmerPayload(
                    launcher_id=bytes32.zeros,
                    payout_instructions=wallet_address2,
                    suggested_difficulty=uint64(10),
                ),
                signature=G2Element(),  # TODO
                authentication_token=login_response.authentication_token,
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            PutFarmerResponse.from_json_dict(await resp.json())
        async with session.get(
            "https://localhost:8080/v2/get_farmer",
            json=GetFarmerRequest(
                launcher_id=bytes32.zeros, authentication_token=login_response.authentication_token
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            farmer_response = GetFarmerResponse.from_json_dict(await resp.json())
            assert farmer_response == GetFarmerResponse(
                authentication_public_key=SK.get_g1(),
                payout_instructions=wallet_address2,
                current_difficulty=uint64(10),
            )
        async with session.post(
            "https://localhost:8080/v2/post_partial",
            json=PostPartialRequest(
                payload=PartialPayload(
                    launcher_id=bytes32.zeros,
                    proof_of_space=ProofOfSpace(  # TODO
                        challenge=bytes32.zeros,
                        pool_public_key=None,
                        pool_contract_puzzle_hash=None,
                        plot_public_key=SK.get_g1(),
                        version=uint8(0),
                        plot_index=uint16(0),
                        meta_group=uint8(0),
                        strength=uint8(0),
                        size=uint8(0),
                        proof=b"",
                    ),
                    sp_hash=bytes32.zeros,
                    end_of_sub_slot=False,
                    harvester_id=bytes32.zeros,
                ),
                aggregate_signature=G2Element(),  # TODO
                authentication_token=login_response.authentication_token,
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            PostPartialResponse.from_json_dict(await resp.json())

        # Test authentication token expiration
        current_time.return_value += 1
        async with session.get(
            "https://localhost:8080/v2/get_farmer",
            json=GetFarmerRequest(
                launcher_id=bytes32.zeros, authentication_token=login_response.authentication_token
            ).to_json_dict(),
            ssl=False,
        ) as resp:
            error_response = ErrorResponse.from_json_dict(await resp.json())
            assert error_response == ErrorResponse(
                error_code=uint16(PoolErrorCode.INVALID_AUTHENTICATION_TOKEN.value),
                error_message=f"Invalid authentication token for launcher_id {bytes32.zeros.hex()}.",
            )
