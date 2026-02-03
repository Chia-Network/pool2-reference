from __future__ import annotations

from typing import Protocol, Self

from api.node import FullNode
from api.store import Store
from api.wallet import Wallet
from typing_extensions import TypedDict, Unpack


class CreatService(TypedDict):
    store: Store
    node: FullNode
    wallet: Wallet


class Service(Protocol):
    @classmethod
    def create(cls, **kwargs: Unpack[CreatService]) -> Self: ...
    def confirm_partials(self) -> None: ...
    def collect_pool_rewards(self) -> None: ...
    def submit_payments(self) -> None: ...
