from __future__ import annotations

import asyncio
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
import yaml
from api.server import APIEndpointMetadata
from chia.util.streamable import Streamable, streamable
from chia_rs.sized_bytes import bytes32
from server.config import CONFIG_FILE_NAME
from server.farmer_rpc import FarmerRPCServer
from server.pooling_tasks import PoolServer


@pytest.fixture
def config_fixture(tmp_path: pathlib.Path) -> Iterator[None]:
    config_path = pathlib.Path.home().joinpath(CONFIG_FILE_NAME)
    try:
        config_path.touch()
        with config_path.open(mode="w") as file:
            TODO = 0
            yaml.dump(
                {
                    "logging": {
                        "log_level": "DEBUG",
                        "log_stdout": True,
                        "log_syslog": True,
                        "log_syslog_host": "",
                        "log_syslog_port": TODO,
                        "log_filename": "",
                        "log_maxfilesrotation": TODO,
                        "log_max_bytes_rotation": TODO,
                        "log_use_gzip": True,
                    },
                    "pool_info": {
                        "name": "",
                        "log_url": "https://foo.com",
                        "description": "",
                        "welcome_message": "",
                    },
                    "web_config": {
                        "host": "localhost",
                        "port": 8080,
                        # TODO: don't rely on chia config here
                        "ssl_cert_path": str(
                            pathlib.Path.home().joinpath(".chia/mainnet/config/ssl/ca/private_ca.crt")
                        ),
                        "ssl_key_path": str(pathlib.Path.home().joinpath(".chia/mainnet/config/ssl/ca/private_ca.key")),
                    },
                    "service_loop_intervals": 1,
                    "authentication_token_timeout": 0,
                },
                file,
            )
        yield
    finally:
        if config_path.exists():
            config_path.unlink()


@pytest.mark.anyio
async def test_server(config_fixture: None) -> None:
    service_mock = AsyncMock()
    call_count = 0

    NUMBER_OF_LOOPS = 3
    NUMBER_OF_SERVICE_ENDPOINTS = 4

    async def fake_sleep(_: int) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= NUMBER_OF_LOOPS * NUMBER_OF_SERVICE_ENDPOINTS:
            raise RuntimeError("Stop loop")
        await asyncio.sleep(0)

    with patch("server.pooling_tasks.sleep", new=fake_sleep):
        async with PoolServer.create_pool_tasks(service=service_mock):
            for _ in range(NUMBER_OF_LOOPS):
                await asyncio.sleep(0)
            assert call_count == NUMBER_OF_SERVICE_ENDPOINTS * NUMBER_OF_LOOPS
            assert service_mock.confirm_partials.call_count == NUMBER_OF_LOOPS
            assert service_mock.collect_pool_rewards.call_count == NUMBER_OF_LOOPS
            assert service_mock.submit_payments.call_count == NUMBER_OF_LOOPS
            assert service_mock.check_for_singletons.call_count == NUMBER_OF_LOOPS


@streamable
@dataclass(frozen=True, kw_only=True)
class V1EndpointRequest(Streamable):
    v1_argument: str


@streamable
@dataclass(frozen=True, kw_only=True)
class V1EndpointResponse(Streamable):
    v1_response: str
    token_sk: bytes32


@streamable
@dataclass(frozen=True, kw_only=True)
class V2EndpointRequest(Streamable):
    v2_argument: str


@streamable
@dataclass(frozen=True, kw_only=True)
class V2EndpointResponse(Streamable):
    v2_response: str
    token_sk: bytes32


@pytest.mark.anyio
async def test_rpc_server(config_fixture: None) -> None:
    async def v1_handler(request: V1EndpointRequest, token_sk: bytes32) -> V1EndpointResponse:  # noqa: RUF029
        return V1EndpointResponse(v1_response=request.v1_argument, token_sk=token_sk)

    async def v2_handler(request: V2EndpointRequest, token_sk: bytes32) -> V2EndpointResponse:  # noqa: RUF029
        return V2EndpointResponse(v2_response=request.v2_argument, token_sk=token_sk)

    async with (
        FarmerRPCServer.create_rpc(
            farmer_rpcs={
                "v1": [
                    APIEndpointMetadata(
                        endpoint_name="test_endpoint",
                        request_type="GET",
                        request=V1EndpointRequest,
                        response=V1EndpointResponse,
                    )
                ],
                "v2": [
                    APIEndpointMetadata(
                        endpoint_name="test_endpoint",
                        request_type="GET",
                        request=V2EndpointRequest,
                        response=V2EndpointResponse,
                    )
                ],
            },
            handlers={"v1": {"test_endpoint": v1_handler}, "v2": {"test_endpoint": v2_handler}},
            token_sk=bytes32.zeros,
        ),
        aiohttp.ClientSession() as session,
    ):
        for version_string, response_prefix in (("", "v1"), ("/v1", "v1"), ("/v2", "v2")):
            async with session.get(
                f"https://localhost:8080{version_string}/test_endpoint",
                json={f"{response_prefix}_argument": version_string},
                ssl=False,
            ) as resp:
                assert await resp.json() == {
                    f"{response_prefix}_response": version_string,
                    "token_sk": "0x" + bytes32.zeros.hex(),
                }
