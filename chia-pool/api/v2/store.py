from __future__ import annotations

from typing import Protocol

from chia_rs import G1Element
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint32, uint64
from typing_extensions import NotRequired, TypedDict, Unpack


# API
class AddFarmer(TypedDict):
    version: uint8
    launcher_id: bytes32
    user_puzzle_hash: bytes32
    payout_instructions: str
    difficulty: uint64
    authentication_public_key: G1Element


class GetFarmer(TypedDict):
    launcher_id: bytes32


class GetFarmerResponse(TypedDict):
    user_puzzle_hash: bytes32
    payout_instructions: str
    difficulty: uint64
    authentication_public_key: G1Element


class UpdateDifficulty(TypedDict):
    launcher_id: bytes32
    difficulty: uint64


class AddSingleton(TypedDict):
    launcher_id: bytes32
    coin_id: bytes32
    exiting_height: uint32 | None


class GetLauncherIDs(TypedDict):
    start: NotRequired[uint64]
    count: NotRequired[uint64]


class GetLauncherIDsResponse(TypedDict):
    launcher_ids: list[bytes32]


class AddPartial(TypedDict):
    launcher_id: bytes32
    timestamp: uint64
    difficulty: uint64


class GetPartials(TypedDict):
    launcher_id: bytes32
    count: NotRequired[uint64]
    since_last_payout: NotRequired[bool]


class ConfirmPartials(TypedDict):
    launcher_id: bytes32
    until_timestamp: uint64


class DeletePartial(TypedDict):
    launcher_id: bytes32
    timestamp: uint64


class PartialMetadata(TypedDict):
    timestamp: uint64
    difficulty: uint64


class GetPartialsResponse(TypedDict):
    partials: list[PartialMetadata]


class AddPayout(TypedDict):
    launcher_id: bytes32
    timestamp: uint64
    payout_details: str


# Stubs
class Store(Protocol):
    def add_farmer(self, **kwargs: Unpack[AddFarmer]) -> None: ...
    def get_farmer(self, **kwargs: Unpack[GetFarmer]) -> GetFarmerResponse: ...
    def update_difficulty(self, **kwargs: Unpack[UpdateDifficulty]) -> None: ...
    def add_singleton(self, **kwargs: Unpack[AddSingleton]) -> None: ...
    def get_launcher_ids(self, **kwargs: Unpack[GetLauncherIDs]) -> GetLauncherIDsResponse: ...
    def add_partial(self, **kwargs: Unpack[AddPartial]) -> None: ...
    def get_partials(self, **kwargs: Unpack[GetPartials]) -> GetPartialsResponse: ...
    def confirm_partials(self, **kwargs: Unpack[ConfirmPartials]) -> None: ...
    def add_payout(self, **kwargs: Unpack[AddPayout]) -> None: ...
