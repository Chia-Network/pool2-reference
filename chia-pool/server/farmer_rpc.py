from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from types import NoneType
from typing import Any, get_type_hints

from aiohttp import web
from api.farmer_protocols.rest import APIEndpointMetadata, ErrorResponse, FarmerRPCError, PoolErrorCode
from api.server import VersionString
from api.service import Service
from chia.util.streamable import Streamable
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint16
from server.config import Config, canonical_load_config
from server.logging import setup_logging


def _wrap_http_handler(
    func: Callable[[Streamable | None, Service, Config, bytes32], Coroutine[Any, Any, Streamable | None]],
    service: Service,
    config: Config,
    token_sk: bytes32,
    logger: logging.Logger,
) -> Callable[[web.Request], Coroutine[Any, Any, web.Response]]:
    hints = get_type_hints(func)
    request_class = hints["request"]

    async def inner(request: web.Request) -> web.Response:
        logger.info("Calling endpoint: %s", func.__qualname__)
        try:
            if request_class is NoneType:
                deserialized_request = None
            else:
                request_json = await request.json()
                logger.debug("Request content: %s", request_json)
                assert issubclass(request_class, Streamable)
                deserialized_request = request_class.from_json_dict(request_json)  # type: ignore[arg-type]
            res_object = await func(deserialized_request, service, config, token_sk)
        except FarmerRPCError as e:
            logger.error("Error from endpoint %s", func.__qualname__)
            res_object = ErrorResponse(error_code=uint16(e.code.value), error_message=e.message)
        except Exception as e:
            logger.exception("Exception from endpoint %s", func.__qualname__)
            if len(e.args) > 0:
                res_object = ErrorResponse(
                    error_code=uint16(PoolErrorCode.SERVER_EXCEPTION.value), error_message=f"{e.args[0]}"
                )
            else:
                res_object = ErrorResponse(
                    error_code=uint16(PoolErrorCode.SERVER_EXCEPTION.value), error_message=f"{e}"
                )
        response_json = res_object.to_json_dict() if res_object is not None else None
        logger.debug("Response content: %s", response_json)
        res = web.Response() if response_json is None else web.json_response(data=response_json)
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    return inner


class FarmerRPCServer:
    runner: web.BaseRunner
    site: web.TCPSite
    logger: logging.Logger

    @classmethod
    @asynccontextmanager
    async def create_rpc(
        cls,
        *,
        farmer_rpcs: dict[VersionString, list[APIEndpointMetadata]],
        handlers: dict[
            VersionString,
            dict[str, Callable[[Streamable | None, Service, Config, bytes32], Coroutine[Any, Any, Streamable | None]]],
        ],
        service: Service,
        token_sk: bytes32,
    ) -> AsyncIterator[None]:
        self = cls()
        config = canonical_load_config()
        self.logger = logging.getLogger("farmer_rpc")
        setup_logging(self.logger, config["logging"])
        app = web.Application()
        for version_string, endpoint_metadatas in farmer_rpcs.items():
            self.logger.debug("Adding routes for version %s", version_string)
            for route in endpoint_metadatas:
                handler = _wrap_http_handler(
                    handlers[version_string][route.endpoint_name], service, config, token_sk, self.logger
                )
                app.router.add_route(
                    method=route.request_type,
                    path=f"/{version_string}/{route.endpoint_name}",
                    handler=handler,
                )
                if version_string == "v1":  # for backwards compatibility, we put v1 endpoints on / as well
                    app.router.add_route(
                        method=route.request_type,
                        path=f"/{route.endpoint_name}",
                        handler=handler,
                    )
        self.runner = web.AppRunner(app, access_log=None)
        try:
            self.logger.info("Setting up AppRunner")
            await self.runner.setup()
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.logger.debug(
                "Loading cert chain from %s and %s",
                config["web_config"]["ssl_cert_path"],
                config["web_config"]["ssl_key_path"],
            )
            ssl_context.load_cert_chain(config["web_config"]["ssl_cert_path"], config["web_config"]["ssl_key_path"])
            self.site = web.TCPSite(
                self.runner,
                host=config["web_config"]["host"],
                port=config["web_config"]["port"],
                ssl_context=ssl_context,
            )
            self.logger.info("Starting TCPSite")
            await self.site.start()
            yield None
        finally:
            self.logger.debug("Cleaning up AppRunner")
            await self.runner.cleanup()
