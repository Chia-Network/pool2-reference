from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def create_config(filename: str) -> Iterator[None]:
    try:
        yield None
    finally:
        if pathlib.Path.cwd().joinpath(filename).exists():
            pathlib.Path.cwd().joinpath(filename).unlink()
