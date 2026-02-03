from __future__ import annotations

from typing import Protocol, Self

from api.rest import APIEndpoint
from api.v2.config import Config
from api.v2.node import FullNode
from api.v2.service import Service
from api.v2.store import Store
from api.v2.wallet import Wallet
from typing_extensions import TypedDict, Unpack

VersionString = str


class CreateServer(TypedDict):
    config: Config
    farmer_rps: dict[VersionString, list[APIEndpoint]]
    node: FullNode
    service: Service
    store: Store
    wallet: Wallet


class Server(Protocol):
    @classmethod
    def create(cls, **kwargs: Unpack[CreateServer]) -> Self: ...
    def start_pool_tasks(self) -> None: ...
    def stop_pool_tasks(self) -> None: ...
    def start_farmer_rpc(self) -> None: ...
    def stop_farmer_rpc(self) -> None: ...
