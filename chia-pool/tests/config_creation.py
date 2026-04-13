from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def create_config(filename: str) -> Iterator[pathlib.Path]:
    config_path = pathlib.Path.cwd().joinpath(filename)
    try:
        config_path.touch()
        yield config_path
    finally:
        if config_path.exists():
            config_path.unlink()
