from __future__ import annotations

from collections.abc import Iterator

import pytest
import yaml
from chia._tests.environments.wallet import WalletTestFramework
from tests.config_creation import create_config
from wallet.config import CONFIG_FILE_NAME


@pytest.fixture
def wallet_config(wallet_envs: WalletTestFramework) -> Iterator[None]:
    env = wallet_envs.environments[0]
    with create_config(CONFIG_FILE_NAME) as config_path, config_path.open(mode="w", encoding="utf8") as file:
        yaml.dump(
            {
                "self_hostname": "127.0.0.1",
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
        yield None
