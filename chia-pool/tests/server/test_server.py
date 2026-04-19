from __future__ import annotations

import asyncio
import pathlib
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from api.server import APIEndpointMetadata, Config
from api.service import Service
from chia.util.streamable import Streamable, streamable
from chia_rs.sized_bytes import bytes32
from server.farmer_rpc import FarmerRPCServer
from server.pooling_tasks import PoolServer


@pytest.mark.anyio
async def test_server(server_config: None, root_path: pathlib.Path) -> None:
    service_mock = AsyncMock()
    call_count = 0

    service_mock.confirm_partials.__qualname__ = "confirm_partials"
    service_mock.collect_pool_rewards.__qualname__ = "collect_pool_rewards"
    service_mock.submit_payments.__qualname__ = "submit_payments"
    service_mock.check_for_singletons.__qualname__ = "check_for_singletons"

    NUMBER_OF_LOOPS = 3
    NUMBER_OF_SERVICE_ENDPOINTS = 4

    async def fake_sleep(_: int) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= NUMBER_OF_LOOPS * NUMBER_OF_SERVICE_ENDPOINTS:
            raise RuntimeError("Stop loop")
        await asyncio.sleep(0)

    with patch("server.pooling_tasks.sleep", new=fake_sleep):
        async with PoolServer.create_pool_tasks(service=service_mock, root_path=root_path):
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
async def test_rpc_server(server_config: None, root_path: pathlib.Path) -> None:
    async def v1_handler(  # noqa: RUF029
        request: V1EndpointRequest, service: Service, config: Config, token_sk: bytes32
    ) -> V1EndpointResponse:
        return V1EndpointResponse(v1_response=request.v1_argument, token_sk=token_sk)

    async def v2_handler(  # noqa: RUF029
        request: V2EndpointRequest, service: Service, config: Config, token_sk: bytes32
    ) -> V2EndpointResponse:
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
            service=AsyncMock(),
            token_sk=bytes32.zeros,
            root_path=root_path,
        ) as farmer_rpc,
        aiohttp.ClientSession() as session,
    ):
        # not sure what pyright is on about, this works fine
        port = farmer_rpc.site._server.sockets[0].getsockname()[1]  # type: ignore  # noqa: PGH003
        for version_string, response_prefix in (("", "v1"), ("/v1", "v1"), ("/v2", "v2")):
            async with session.get(
                f"https://localhost:{port}{version_string}/test_endpoint",
                json={f"{response_prefix}_argument": version_string},
                ssl=False,
            ) as resp:
                assert await resp.json() == {
                    f"{response_prefix}_response": version_string,
                    "token_sk": "0x" + bytes32.zeros.hex(),
                }
