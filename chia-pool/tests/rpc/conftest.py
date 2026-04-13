from __future__ import annotations

import unittest
from collections.abc import Iterator

import pytest
from chia.util.timing import adjusted_timeout


@pytest.fixture(autouse=True)
def _patch_adjusted_timeout_longer() -> Iterator[None]:
    def new_adjusted_timeout(timeout: float | None) -> float | None:
        if timeout is None:
            return None
        return adjusted_timeout(timeout) + 15

    with unittest.mock.patch("chia.simulator.full_node_simulator.adjusted_timeout", side_effect=new_adjusted_timeout):
        yield
