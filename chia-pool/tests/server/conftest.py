from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
from api.server import CONFIG_FILE_NAME
from click.testing import CliRunner
from reference import cli
from tests.config_creation import create_config


@pytest.fixture
def server_config(generate_ssl_cert: tuple[pathlib.Path, pathlib.Path]) -> Iterator[None]:
    ssl_cert_path, ssl_key_path = generate_ssl_cert
    with create_config(CONFIG_FILE_NAME):
        result = CliRunner().invoke(
            cli,
            [
                "config",
                "server",
                "--root-path",
                str(pathlib.Path.cwd()),
                "--log-level",
                "DEBUG",
                "--log-stdout",
                "--no-log-syslog",
                "--log-syslog-host",
                "",
                "--log-syslog-port",
                "0",
                "--log-filename",
                "",
                "--log-maxfilesrotation",
                "0",
                "--log-max-bytes-rotation",
                "0",
                "--log-use-gzip",
                "--pool-name",
                "",
                "--pool-logo-url",
                "https://foo.com",
                "--pool-description",
                "",
                "--pool-welcome-message",
                "",
                "--web-host",
                "localhost",
                "--web-port",
                "0",
                "--ssl-cert-path",
                str(ssl_cert_path),
                "--ssl-key-path",
                str(ssl_key_path),
                "--service-loop-intervals",
                "1",
                "--authentication-token-timeout",
                "1",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        yield None
