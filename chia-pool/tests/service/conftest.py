from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import PropertyMock, patch

import pytest
import yaml
from api.service import Service as ServiceAPI
from chia._tests.environments.wallet import WalletTestFramework
from chia_rs.sized_ints import uint64
from node.rpc_wrapper import NodeRPC
from service.config import CONFIG_FILE_NAME
from service.service import Service
from store.sqlite import Store
from tests.config_creation import create_config
from wallet.rpc_wrapper import WalletRPC


@pytest.fixture
async def service_config(wallet_envs: WalletTestFramework) -> AsyncIterator[None]:
    env = wallet_envs.environments[0]
    async with env.wallet_state_manager.new_action_scope(tx_config=wallet_envs.tx_config, push=True) as action_scope:
        puzzle_hash = await action_scope.get_puzzle_hash(env.wallet_state_manager)
    with create_config(CONFIG_FILE_NAME) as config_path, config_path.open(mode="w", encoding="utf8") as file:
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
        yield None


@pytest.fixture
async def reference_service(
    store_config: None,
    wallet_config: None,
    full_node_config: None,
    service_config: None,
    wallet_envs: WalletTestFramework,
) -> AsyncIterator[tuple[ServiceAPI, PropertyMock]]:
    async with NodeRPC.create() as node_rpc, WalletRPC.create() as wallet_rpc, Store.create() as store:
        # mock in a timestamp
        with patch.object(Service, "current_time", new_callable=PropertyMock) as current_time:
            service = Service.create(store=store, full_node=node_rpc, wallet=wallet_rpc)
            current_time.return_value = uint64(service.config["partial_confirmation_delay"])
            await wallet_envs.full_node.wait_for_wallet_synced(wallet_node=wallet_envs.environments[0].node)
            yield service, current_time
