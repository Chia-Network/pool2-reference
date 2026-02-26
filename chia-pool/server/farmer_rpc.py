from __future__ import annotations

import ssl
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, get_type_hints

from aiohttp import web
from api.farmer_protocols.rest import APIEndpointMetadata
from api.farmer_protocols.v2.farmer import ErrorResponse, PoolErrorCode
from api.server import VersionString
from chia.util.streamable import Streamable
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16
from server.config import canonical_load_config


def _wrap_http_handler(
    func: Callable[[Streamable | None, bytes32], Coroutine[Any, Any, Streamable | None]], token_sk: bytes32
) -> Callable[[web.Request], Coroutine[Any, Any, web.Response]]:
    hints = get_type_hints(func)
    request_class = hints["request"]

    async def inner(request: web.Request) -> web.Response:
        try:
            if request_class is None:
                deserialized_request = None
            else:
                assert issubclass(request_class, Streamable)
                deserialized_request = request_class.from_json_dict(await request.json())  # type: ignore[arg-type]
            res_object = await func(deserialized_request, token_sk)
        except Exception as e:
            if len(e.args) > 0:
                res_object = ErrorResponse(
                    error_code=uint16(PoolErrorCode.SERVER_EXCEPTION.value), error_message=f"{e.args[0]}"
                )
            else:
                res_object = ErrorResponse(
                    error_code=uint16(PoolErrorCode.SERVER_EXCEPTION.value), error_message=f"{e}"
                )
        res = web.Response() if res_object is None else web.json_response(data=res_object.to_json_dict())
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    return inner


class FarmerRPCServer:
    runner: web.BaseRunner
    site: web.TCPSite

    @classmethod
    @asynccontextmanager
    async def create_rpc(
        cls,
        *,
        farmer_rpcs: dict[VersionString, list[APIEndpointMetadata]],
        handlers: dict[
            VersionString,
            dict[str, Callable[[Streamable | None, bytes32], Coroutine[Any, Any, Streamable | None]]],
        ],
        token_sk: bytes32,
    ) -> AsyncIterator[None]:
        self = cls()
        config = canonical_load_config()
        app = web.Application()
        for version_string, endpoint_metadatas in farmer_rpcs.items():
            for route in endpoint_metadatas:
                handler = _wrap_http_handler(handlers[version_string][route.endpoint_name], token_sk)
                app.router.add_route(
                    method=route.request_type,
                    path=f"/{version_string}/{route.endpoint_name}",
                    handler=handler,
                )
                if version_string == "v1":
                    app.router.add_route(
                        method=route.request_type,
                        path=f"/{route.endpoint_name}",
                        handler=handler,
                    )
        self.runner = web.AppRunner(app, access_log=None)
        try:
            await self.runner.setup()
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(config["web_config"]["ssl_cert_path"], config["web_config"]["ssl_key_path"])
            self.site = web.TCPSite(
                self.runner,
                host=config["web_config"]["host"],
                port=config["web_config"]["port"],
                ssl_context=ssl_context,
            )
            await self.site.start()
            yield None
        finally:
            await self.runner.cleanup()
