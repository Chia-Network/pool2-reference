from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
from click.testing import CliRunner

from chia_pool._tests.config_creation import create_config
from chia_pool.api.store import CONFIG_FILE_NAME
from chia_pool.reference import cli


@pytest.fixture
def store_config() -> Iterator[None]:
    with create_config(CONFIG_FILE_NAME):
        result = CliRunner().invoke(
            cli,
            [
                "config",
                "store",
                "--root-path",
                str(pathlib.Path.cwd()),
                "--store-path",
                str(pathlib.Path.cwd().joinpath("store.sqlite")),
            ],
        )
        assert result.exit_code == 0, result.output
        yield None
