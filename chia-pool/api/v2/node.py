from __future__ import annotations

from chia_rs import CoinRecord
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32
from typing_extensions import TypedDict, Unpack


# API
class GetBlockchainStateResponse(TypedDict):
    peak: uint32
    synced: bool


class GetCoinRecordsByPuzzleHashes(TypedDict):
    puzzle_hashes: list[bytes32]


class GetCoinRecordsByPuzzleHashesResponse(TypedDict):
    coin_records: list[CoinRecord]


class GetCoinRecordByName(TypedDict):
    coin_id: bytes32


class GetCoinRecordByNameResponse(TypedDict):
    coin_records: CoinRecord


class GetRecentSignagePoint(TypedDict):
    signage_point_hash: bytes32


class GetRecentEndOfSubslot(TypedDict):
    challenge_hash: bytes32


class GetRecentSignagePointOrEOSResponse(TypedDict):
    exists: bool
    reverted: bool


# Stubs
class FullNode:
    def get_blockchain_state(self) -> GetBlockchainStateResponse: ...
    def get_coin_records_by_puzzle_hashes(
        self, **kwargs: Unpack[GetCoinRecordsByPuzzleHashes]
    ) -> GetCoinRecordsByPuzzleHashesResponse: ...
    def get_coin_record_by_name(self, **kwargs: Unpack[GetCoinRecordByName]) -> GetCoinRecordByNameResponse: ...
    def get_recent_signage_point(
        self, **kwargs: Unpack[GetRecentSignagePoint]
    ) -> GetRecentSignagePointOrEOSResponse: ...
    def get_recent_end_of_subslot(
        self, **kwargs: Unpack[GetRecentEndOfSubslot]
    ) -> GetRecentSignagePointOrEOSResponse: ...
