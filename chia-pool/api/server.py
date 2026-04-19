from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Literal, Protocol, TypedDict

from api.service import Service
from chia.util.streamable import Streamable
from chia_rs.sized_bytes import bytes32
from farmer_rpc.api import APIEndpointMetadata

VersionString = str


class TaskServer(Protocol):
    @classmethod
    @asynccontextmanager
    async def create_pooling_tasks(cls, *, service: Service, root_path: pathlib.Path) -> AsyncIterator[None]:
        yield None


class RPCServer(Protocol):
    @asynccontextmanager
    async def create_rpc(
        self,
        *,
        farmer_rpcs: dict[VersionString, list[APIEndpointMetadata]],
        handlers: dict[VersionString, dict[str, Callable[[Streamable | None], Coroutine[Any, Any, Streamable | None]]]],
        token_sk: bytes32,
        root_path: pathlib.Path,
    ) -> AsyncIterator[None]:
        yield None


CONFIG_FILE_NAME = "pool_server_config.yaml"


class LoggingConfig(TypedDict):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    log_stdout: bool
    log_syslog: bool
    log_syslog_host: str
    log_syslog_port: int
    log_filename: str
    log_maxfilesrotation: int
    log_max_bytes_rotation: int
    log_use_gzip: bool


class PoolInfoConfig(TypedDict):
    name: str
    logo_url: str
    description: str
    welcome_message: str


class WebConfig(TypedDict):
    host: str
    port: int
    ssl_cert_path: str
    ssl_key_path: str


class Config(TypedDict):
    logging: LoggingConfig
    pool_info: PoolInfoConfig
    service_loop_intervals: int
    web_config: WebConfig
    authentication_token_timeout: int
