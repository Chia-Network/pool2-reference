from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol, Self

from chia_rs import SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64
from typing_extensions import TypedDict


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
    async def create(cls) -> AsyncIterator[Self]:
        yield cls()

    async def send_transaction(self, *, payments: list[Payment], fee: uint64) -> SendTransactionResponse: ...
    async def submit_transaction(self, *, spend_bundle: SpendBundle, fee: uint64) -> SubmitTransactionResponse: ...
    async def get_transaction_status(self, *, tx_id: bytes32) -> GetTransactionStatusResponse: ...
