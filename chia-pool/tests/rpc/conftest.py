from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator, Iterator
from unittest.mock import PropertyMock, patch

import pytest
from api.service import Service as ServiceAPI
from chia.util.timing import adjusted_timeout
from chia_rs.sized_bytes import bytes32
from farmer_rpc.v2 import HANDLERS, METADATA
from server.farmer_rpc import FarmerRPCServer


@pytest.fixture(autouse=True)
def _patch_adjusted_timeout_longer() -> Iterator[None]:
    def new_adjusted_timeout(timeout: float | None) -> float | None:
        if timeout is None:
            return None
        return adjusted_timeout(timeout) + 30

    with patch("chia.simulator.full_node_simulator.adjusted_timeout", side_effect=new_adjusted_timeout):
        yield


@pytest.fixture
async def farmer_rpc_url(
    server_config: None, reference_service: tuple[ServiceAPI, PropertyMock], root_path: pathlib.Path
) -> AsyncIterator[str]:
    service, _ = reference_service
    async with FarmerRPCServer.create_rpc(
        farmer_rpcs={"v2": METADATA},
        handlers={"v2": HANDLERS},
        service=service,
        token_sk=bytes32.zeros,
        root_path=root_path,
    ) as farmer_rpc:
        # not sure what pyright is on about, this works fine
        port = farmer_rpc.site._server.sockets[0].getsockname()[1]  # type: ignore  # noqa: PGH003
        yield f"https://localhost:{port}"
