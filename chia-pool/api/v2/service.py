from __future__ import annotations

from typing import Protocol

from api.rest import APIEndpoint
from api.v2.config import Config
from api.v2.node import FullNode
from api.v2.store import Store
from api.v2.wallet import Wallet
from typing_extensions import TypedDict, Unpack


# API
class ConfirmPartials(TypedDict):
    config: Config
    store: Store
    node: FullNode


class CollectPoolRewards(TypedDict):
    config: Config
    store: Store
    node: FullNode


class SubmitPayments(TypedDict):
    config: Config
    store: Store
    wallet: Wallet


class HandleRequests(TypedDict):
    config: Config
    store: Store
    protocol_apis: dict[str, list[APIEndpoint]]


# Stubs
class Service(Protocol):
    def confirm_partials(self, **kwargs: Unpack[ConfirmPartials]) -> None:
        pass

    def collect_pool_rewards(self, **kwargs: Unpack[CollectPoolRewards]) -> None:
        pass

    def submit_payments(self, **kwargs: Unpack[SubmitPayments]) -> None:
        pass

    def handle_requests(self, **kwargs: Unpack[HandleRequests]) -> None:
        pass
