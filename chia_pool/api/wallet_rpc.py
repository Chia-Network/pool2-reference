from __future__ import annotations

import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from chia_rs import SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64
from typing_extensions import NotRequired, Self, TypedDict

from chia_pool.api.rpc import NetConfig


# API
@dataclass(frozen=True, kw_only=True)
class Payment:
    amount: uint64
    puzzle_hash: bytes32
    memos: list[str] | None


class SendTransactionResponse(TypedDict):
    tx_ids: list[bytes32]


class SubmitTransactionResponse(TypedDict):
    tx_id: bytes32


class GetTransactionStatusResponse(TypedDict):
    confirmed: bool


# Stubs
class Wallet(Protocol):
    @classmethod
    @asynccontextmanager
    async def create(cls, root_path: pathlib.Path) -> AsyncIterator[Self]:
        yield cls()

    async def send_transaction(self, *, payments: list[Payment], fee: uint64) -> SendTransactionResponse: ...
    async def submit_transaction(self, *, spend_bundle: SpendBundle, fee: uint64) -> SubmitTransactionResponse: ...
    async def get_transaction_status(self, *, tx_id: bytes32) -> GetTransactionStatusResponse: ...


class TXConfig(TypedDict):
    min_coin_amount: NotRequired[int]
    max_coin_amount: NotRequired[int]
    excluded_coin_amounts: NotRequired[list[int]]
    excluded_coin_ids: NotRequired[list[str]]
    reuse_puzhash: NotRequired[bool]


class Config(TypedDict):
    self_hostname: str
    rpc_port: int
    root_path: str
    net_config: NetConfig
    tx_config: TXConfig


CONFIG_FILE_NAME = "pool_wallet_client_config.yaml"
