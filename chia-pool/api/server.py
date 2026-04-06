from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Protocol

from api.service import Service
from chia.util.streamable import Streamable
from chia_rs.sized_bytes import bytes32
from farmer_rpc.api import APIEndpointMetadata

VersionString = str


class TaskServer(Protocol):
    @classmethod
    @asynccontextmanager
    async def create_pooling_tasks(cls, *, service: Service) -> AsyncIterator[None]:
        yield None


class RPCServer(Protocol):
    @asynccontextmanager
    async def create_rpc(
        self,
        *,
        farmer_rpcs: dict[VersionString, list[APIEndpointMetadata]],
        handlers: dict[VersionString, dict[str, Callable[[Streamable | None], Coroutine[Any, Any, Streamable | None]]]],
        token_sk: bytes32,
    ) -> AsyncIterator[None]:
        yield None
