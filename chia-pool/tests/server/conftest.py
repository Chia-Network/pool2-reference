from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
import yaml
from server.config import CONFIG_FILE_NAME
from tests.config_creation import create_config


@pytest.fixture
def server_config(generate_ssl_cert: tuple[pathlib.Path, pathlib.Path]) -> Iterator[None]:
    ssl_cert_path, ssl_key_path = generate_ssl_cert
    with create_config(CONFIG_FILE_NAME) as config_path, config_path.open(mode="w", encoding="utf8") as file:
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
        yield None
