from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from chia.util.streamable import Streamable, streamable
from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from typing_extensions import Self, TypedDict


# Responses
class GetFarmerResponse(TypedDict):
    version: uint8
    payout_instructions: str
    difficulty: uint64
    authentication_public_key: G1Element


class GetLauncherIDsResponse(TypedDict):
    launcher_ids: list[bytes32]


class GetLatestSingletonResponse(TypedDict):
    coin_id: bytes32
    created_height: uint32
    exiting_height: uint32 | None


@streamable
@dataclass(frozen=True, kw_only=True)
class PartialMetadata(Streamable):
    timestamp: uint64
    difficulty: uint64


class GetPartialsResponse(TypedDict):
    partials: list[PartialMetadata]


class GetLatestPayoutResponse(TypedDict):
    timestamp: uint64
    payout_details: str


class ClaimMetadata(TypedDict):
    timestamp: uint64
    amount: uint64


class GetRewardClaimsResponse(TypedDict):
    claims: list[ClaimMetadata]


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
        self,
        *,
        launcher_id: bytes32,
        confirmed: bool,
        since: uint64 | None = None,
        before: uint64 | None = None,
        count: uint64 | None = None,
    ) -> GetPartialsResponse: ...
    async def confirm_partials(self, *, launcher_id: bytes32, until_timestamp: uint64) -> None: ...
    async def delete_partial(self, *, launcher_id: bytes32, timestamp: uint64) -> None: ...
    async def add_reward_claim(self, *, timestamp: uint64, amount: uint64) -> None: ...
    async def set_claims_statuses(self, *, timestamps: list[uint64]) -> None: ...
    async def get_unpaid_reward_claims(self) -> GetRewardClaimsResponse: ...
    async def add_payout(self, *, timestamp: uint64, payout_details: str) -> None: ...
    async def get_latest_payout(self) -> GetLatestPayoutResponse | None: ...
