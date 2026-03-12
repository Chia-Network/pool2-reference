from __future__ import annotations

from typing import Protocol

from api.node import FullNode
from api.store import Store
from api.wallet import Wallet
from chia_rs.sized_ints import uint64
from service.config import ServiceConfig
from typing_extensions import Self


class Service(Protocol):
    store: Store
    full_node: FullNode
    wallet: Wallet
    config: ServiceConfig

    @property
    def current_time(self) -> uint64: ...
    @classmethod
    def create(cls, *, store: Store, full_node: FullNode, wallet: Wallet) -> Self: ...
    async def confirm_partials(self) -> None: ...
    async def check_for_singletons(self) -> None: ...
    async def collect_pool_rewards(self) -> None: ...
    async def submit_payments(self) -> None: ...
