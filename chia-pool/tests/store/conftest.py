from __future__ import annotations

import pathlib
from collections.abc import Iterator

import pytest
from click.testing import CliRunner
from reference import cli
from store.config import CONFIG_FILE_NAME
from tests.config_creation import create_config


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
