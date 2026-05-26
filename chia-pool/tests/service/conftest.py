from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from api.service import CONFIG_FILE_NAME
from api.service import Service as ServiceAPI
from chia._tests.environments.wallet import WalletTestFramework
from chia.full_node.full_node_rpc_api import FullNodeRpcApi
from chia_rs.sized_ints import uint64, uint128
from click.testing import CliRunner
from node.rpc_wrapper import NodeRPC
from reference import cli
from service.service import Service
from store.sqlite import Store
from tests.config_creation import create_config
from wallet.rpc_wrapper import WalletRPC


@pytest.fixture
async def service_config(wallet_envs: WalletTestFramework) -> AsyncIterator[None]:
    env = wallet_envs.environments[0]
    async with env.wallet_state_manager.new_action_scope(tx_config=wallet_envs.tx_config, push=True) as action_scope:
        puzzle_hash = await action_scope.get_puzzle_hash(env.wallet_state_manager)
    with create_config(CONFIG_FILE_NAME):
        result = CliRunner().invoke(
            cli,
            [
                "config",
                "service",
                "--root-path",
                str(pathlib.Path.cwd()),
                "--relative-lock-height",
                "5",
                "--pool-wallet-address",
                puzzle_hash.hex(),
                "--pool-memoization",
                "80",
                "--min-difficulty",
                "0",
                "--default-difficulty",
                "0",
                "--partial-time-limit",
                "60",
                "--partial-confirmation-delay",
                "600",
                "--scan-start-height",
                "0",
                "--confirmation-security-threshold",
                "0",
                "--max-additions-per-transaction",
                "100",
                "--number-of-partials-target",
                "2",
                "--time-target",
                "2",
                "--fee",
                "1000",
                "--genesis-challenge",
                env.node.constants.GENESIS_CHALLENGE.hex(),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        yield None


@pytest.fixture
async def reference_service(
    store_config: None,
    wallet_config: None,
    full_node_config: None,
    service_config: None,
    wallet_envs: WalletTestFramework,
    root_path: pathlib.Path,
) -> AsyncIterator[tuple[ServiceAPI, PropertyMock]]:
    async with (
        NodeRPC.create(root_path=root_path) as node_rpc,
        WalletRPC.create(root_path=root_path) as wallet_rpc,
        Store.create(root_path=root_path) as store,
    ):
        # mock in a timestamp
        with (
            patch.object(Service, "current_time", new_callable=PropertyMock) as current_time,
            patch.object(
                FullNodeRpcApi,
                "get_network_space",
                new=AsyncMock(return_value={"space": uint128(0)}),
            ),
        ):
            service = Service.create(store=store, full_node=node_rpc, wallet=wallet_rpc, root_path=root_path)
            current_time.return_value = uint64(service.config["partial_confirmation_delay"])
            await wallet_envs.full_node.wait_for_wallet_synced(wallet_node=wallet_envs.environments[0].node)
            yield service, current_time
