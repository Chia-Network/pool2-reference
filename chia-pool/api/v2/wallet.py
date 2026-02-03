from __future__ import annotations

from typing import Protocol, Self

from api.v2.config import Config
from api.v2.store import Store
from chia_rs import SpendBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint64
from typing_extensions import NotRequired, TypedDict, Unpack


# API
class CreateWallet(TypedDict):
    config: Config
    store: Store


class CreateCoin(TypedDict):
    amount: uint64
    puzzle_hash: bytes32
    memos: NotRequired[list[str]]


class SendTransaction(TypedDict):
    payments: list[CreateCoin]
    fee: uint64


class SendTransactionResponse(TypedDict):
    tx_id: bytes32


class SubmitTransaction(TypedDict):
    spend_bundle: SpendBundle


class SubmitTransactionResponse(TypedDict):
    tx_id: bytes32


class GetTransactionStatus(TypedDict):
    tx_id: bytes32


class GetTransactionStatusResponse(TypedDict):
    confirmed: bool


# Stubs
class Wallet(Protocol):
    @classmethod
    def create(cls, **kwargs: Unpack[CreateWallet]) -> Self: ...
    def send_transaction(self, **kwargs: Unpack[SendTransaction]) -> SendTransactionResponse: ...
    def submit_transaction(self, **kwargs: Unpack[SubmitTransaction]) -> SubmitTransactionResponse: ...
    def get_transaction_status(self, **kwargs: Unpack[GetTransactionStatus]) -> GetTransactionStatusResponse: ...
