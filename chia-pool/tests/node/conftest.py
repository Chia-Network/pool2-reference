from __future__ import annotations

from collections.abc import Iterator

import pytest
import yaml
from chia._tests.environments.wallet import WalletTestFramework
from node.config import CONFIG_FILE_NAME
from tests.config_creation import create_config


@pytest.fixture
def full_node_config(wallet_envs: WalletTestFramework) -> Iterator[None]:
    wallet_envs.full_node.full_node.config["selected_network"] = "simulator"
    with create_config(CONFIG_FILE_NAME) as config_path, config_path.open(mode="w", encoding="utf8") as file:
        yaml.dump(
            {
                "self_hostname": "127.0.0.1",
                "rpc_port": wallet_envs.full_node_rpc_client.port,
                "root_path": str(wallet_envs.full_node.full_node.root_path),
                "net_config": {
                    "rpc_timeout": wallet_envs.full_node.config["rpc_timeout"],
                    "daemon_ssl": wallet_envs.full_node.config["daemon_ssl"],
                    "private_ssl_ca": wallet_envs.full_node.config["private_ssl_ca"],
                },
            },
            file,
        )
        yield None
