from __future__ import annotations

from collections.abc import Iterator

import pytest
import yaml
from store.config import CONFIG_FILE_NAME
from tests.config_creation import create_config


@pytest.fixture
def store_config() -> Iterator[None]:
    with create_config(CONFIG_FILE_NAME) as config_path, config_path.open(mode="w", encoding="utf8") as file:
        yaml.dump({"store_path": str(config_path.parent.joinpath("store.sqlite"))}, file)
        yield None
