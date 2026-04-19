from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
from chia._tests.environments.wallet import WalletTestFramework
from click.testing import CliRunner
from reference import cli
from tests.config_creation import create_config
from wallet.config import CONFIG_FILE_NAME


@pytest.fixture
def wallet_config(wallet_envs: WalletTestFramework) -> Iterator[None]:
    env = wallet_envs.environments[0]
    daemon = env.service.config["daemon_ssl"]
    private = env.service.config["private_ssl_ca"]
    with create_config(CONFIG_FILE_NAME):
        result = CliRunner().invoke(
            cli,
            [
                "config",
                "wallet",
                "--root-path",
                str(pathlib.Path.cwd()),
                "--hostname",
                "127.0.0.1",
                "--rpc-port",
                str(env.rpc_server.listen_port),
                "--chia-root",
                str(env.node.root_path),
                "--rpc-timeout",
                str(env.service.config["rpc_timeout"]),
                "--daemon-ssl-crt",
                str(daemon["private_crt"]),
                "--daemon-ssl-key",
                str(daemon["private_key"]),
                "--private-ssl-crt",
                str(private["crt"]),
                "--private-ssl-key",
                str(private["key"]),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        yield None
