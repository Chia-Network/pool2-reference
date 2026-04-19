from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
from chia._tests.environments.wallet import WalletTestFramework
from click.testing import CliRunner
from node.config import CONFIG_FILE_NAME
from reference import cli
from tests.config_creation import create_config


@pytest.fixture
def full_node_config(wallet_envs: WalletTestFramework) -> Iterator[None]:
    wallet_envs.full_node.full_node.config["selected_network"] = "simulator"
    daemon = wallet_envs.full_node.config["daemon_ssl"]
    private = wallet_envs.full_node.config["private_ssl_ca"]
    with create_config(CONFIG_FILE_NAME):
        result = CliRunner().invoke(
            cli,
            [
                "config",
                "node",
                "--root-path",
                str(pathlib.Path.cwd()),
                "--hostname",
                "127.0.0.1",
                "--rpc-port",
                str(wallet_envs.full_node_rpc_client.port),
                "--chia-root",
                str(wallet_envs.full_node.full_node.root_path),
                "--rpc-timeout",
                str(wallet_envs.full_node.config["rpc_timeout"]),
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
