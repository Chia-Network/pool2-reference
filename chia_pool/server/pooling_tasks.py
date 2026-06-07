from __future__ import annotations

import logging
import pathlib
from asyncio import sleep
from asyncio.tasks import Task, create_task
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from chia_pool.api.server import CONFIG_FILE_NAME, Config
from chia_pool.api.service import Service
from chia_pool.config_loading import canonical_load_config
from chia_pool.server.config import ConfigSchema
from chia_pool.server.logging import setup_logging


def _create_loop(
    func: Callable[[], Coroutine[Any, Any, None]], interval: int, logger: logging.Logger
) -> Callable[[], Coroutine[Any, Any, None]]:
    async def looped_func() -> None:
        while True:
            try:
                logger.info("Triggering task %s", func.__qualname__)
                await func()
            except Exception:
                logger.exception("Error in %s", func.__qualname__)
            finally:
                await sleep(interval)

    return looped_func


class PoolServer:
    logger: logging.Logger
    partial_task: Task
    collection_task: Task
    payment_task: Task
    singleton_task: Task

    @classmethod
    @asynccontextmanager
    async def create_pooling_tasks(
        cls,
        *,
        service: Service,
        root_path: pathlib.Path,
    ) -> AsyncIterator[None]:
        self = cls()
        config = canonical_load_config(
            root_path=root_path, config_filename=CONFIG_FILE_NAME, schema_validation=ConfigSchema(), config_type=Config
        )
        self.logger = logging.getLogger("pool_server")
        setup_logging(self.logger, config["logging"])

        self.partial_task = create_task(
            _create_loop(func=service.confirm_partials, interval=config["service_loop_intervals"], logger=self.logger)()
        )
        self.collection_task = create_task(
            _create_loop(
                func=service.collect_pool_rewards, interval=config["service_loop_intervals"], logger=self.logger
            )()
        )
        self.payment_task = create_task(
            _create_loop(func=service.submit_payments, interval=config["service_loop_intervals"], logger=self.logger)()
        )
        self.singleton_task = create_task(
            _create_loop(
                func=service.check_for_singletons, interval=config["service_loop_intervals"], logger=self.logger
            )()
        )
        try:
            yield None
        finally:
            self.logger.debug("Cancelling tasks")
            self.partial_task.cancel()
            self.collection_task.cancel()
            self.payment_task.cancel()
            self.singleton_task.cancel()
