from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol, Self

from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from typing_extensions import TypedDict


# Responses
class GetFarmerResponse(TypedDict):
    version: uint8
    user_puzzle_hash: bytes32
    payout_instructions: str
    difficulty: uint64
    authentication_public_key: G1Element


class GetLauncherIDsResponse(TypedDict):
    launcher_ids: list[bytes32]


class GetLatestSingletonResponse(TypedDict):
    coin_id: bytes32
    created_height: uint32
    exiting_height: uint32 | None


class PartialMetadata(TypedDict):
    timestamp: uint64
    difficulty: uint64


class GetPartialsResponse(TypedDict):
    partials: list[PartialMetadata]


class GetLatestPayoutResponse(TypedDict):
    timestamp: uint64
    payout_details: str


# Stubs
class Store(Protocol):
    @classmethod
    @asynccontextmanager
    async def create(cls) -> AsyncIterator[Self]:
        yield cls()

    async def add_farmer(
        self,
        *,
        version: uint8,
        launcher_id: bytes32,
        user_puzzle_hash: bytes32,
        payout_instructions: str,
        difficulty: uint64,
        authentication_public_key: G1Element,
    ) -> None: ...
    async def get_farmer(self, *, launcher_id: bytes32) -> GetFarmerResponse: ...
    async def update_difficulty(self, *, launcher_id: bytes32, difficulty: uint64) -> None: ...
    async def add_singleton(
        self, *, launcher_id: bytes32, coin_id: bytes32, created_height: uint32, exiting_height: uint32 | None
    ) -> None: ...
    async def get_latest_singleton(self, *, launcher_id: bytes32) -> GetLatestSingletonResponse: ...
    async def get_launcher_ids(
        self, *, start: uint64 | None = None, count: uint64 | None = None
    ) -> GetLauncherIDsResponse: ...
    async def add_partial(self, *, launcher_id: bytes32, timestamp: uint64, difficulty: uint64) -> None: ...
    async def get_partials(
        self, *, launcher_id: bytes32, confirmed: bool, since: uint64 | None = None, before: uint64 | None = None
    ) -> GetPartialsResponse: ...
    async def confirm_partials(self, *, launcher_id: bytes32, until_timestamp: uint64) -> None: ...
    async def delete_partial(self, *, launcher_id: bytes32, timestamp: uint64) -> None: ...
    async def add_payout(self, *, launcher_id: bytes32, timestamp: uint64, payout_details: str) -> None: ...
    async def get_latest_payout(self, *, launcher_id: bytes32) -> GetLatestPayoutResponse | None: ...
