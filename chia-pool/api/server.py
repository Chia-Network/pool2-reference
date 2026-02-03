from __future__ import annotations

from typing import Protocol, Self

from api.farmer_protocols.rest import APIEndpoint
from api.node import FullNode
from api.service import Service
from api.store import Store
from api.wallet import Wallet
from typing_extensions import TypedDict, Unpack

VersionString = str


class CreateServer(TypedDict):
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
