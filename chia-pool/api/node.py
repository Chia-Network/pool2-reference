from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from chia.consensus.signage_point import SignagePoint
from chia_rs import CoinRecord, CoinSpend, EndOfSubSlotBundle
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32, uint64
from typing_extensions import Self, TypedDict


# Responses
class GetBlockchainStateResponse(TypedDict):
    peak: uint32
    synced: bool


class GetCoinRecordsByPuzzleHashesResponse(TypedDict):
    coin_records: list[CoinRecord]


class GetCoinRecordByNameResponse(TypedDict):
    coin_record: CoinRecord


class GetRecentSignagePointOrEOSResponse(TypedDict):
    signage_point: SignagePoint | None
    eos: EndOfSubSlotBundle | None
    time_received: uint64
    exists: bool
    reverted: bool


class GetPuzzleAndSolutionResponse(TypedDict):
    spend: CoinSpend


# Stubs
class FullNode(Protocol):
    @classmethod
    @asynccontextmanager
    async def create(cls) -> AsyncIterator[Self]:
        yield cls()

    async def get_blockchain_state(self) -> GetBlockchainStateResponse: ...
    async def get_coin_records_by_puzzle_hashes(
        self, *, puzzle_hashes: list[bytes32], include_spent_coins: bool, start_height: uint32
    ) -> GetCoinRecordsByPuzzleHashesResponse: ...
    async def get_coin_record_by_name(self, *, coin_id: bytes32) -> GetCoinRecordByNameResponse: ...
    async def get_recent_signage_point(self, *, signage_point_hash: bytes32) -> GetRecentSignagePointOrEOSResponse: ...
    async def get_recent_end_of_subslot(self, *, challenge_hash: bytes32) -> GetRecentSignagePointOrEOSResponse: ...
    async def get_puzzle_and_solution(self, *, coin_id: bytes32, height: uint32) -> GetPuzzleAndSolutionResponse: ...
