from __future__ import annotations

from enum import Enum
from typing import Literal

from api.farmer_protocols.rest import APIEndpointMetadata
from chia_rs import CoinSpend, G1Element, G2Element, ProofOfSpace
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint16, uint32, uint64
from typing_extensions import NotRequired, TypedDict


# Schema
class GetRequest(TypedDict):
    method_name: Literal["get_farmer", "get_login"]
    launcher_id: bytes32
    target_puzzle_hash: bytes32
    authentication_token: uint64


class PoolState(TypedDict):
    version: uint8
    state: uint8
    target_puzzle_hash: bytes32
    owner_pubkey: G1Element
    pool_url: str | None
    relative_lock_height: uint32


class FarmerRecord(TypedDict):
    launcher_id: bytes32
    p2_singleton_puzzle_hash: bytes32
    delay_time: uint64
    delay_puzzle_hash: bytes32
    authentication_public_key: G1Element
    singleton_tip: CoinSpend
    singleton_tip_state: PoolState
    points: uint64
    difficulty: uint64
    payout_instructions: str
    is_pool_member: bool


class GetLoginReponse(TypedDict):
    farmer_record: FarmerRecord | None
    recent_partials: list[tuple[uint64, uint64]] | None


class GetPoolInfoResponse(TypedDict):
    name: str
    logo_url: str
    minimum_difficulty: uint64
    relative_lock_height: uint32
    protocol_version: uint8
    fee: str
    description: str
    target_puzzle_hash: bytes32
    authentication_token_timeout: uint8


class PartialPayload(TypedDict):
    launcher_id: bytes32
    authentication_token: uint64
    proof_of_space: ProofOfSpace
    sp_hash: bytes32
    end_of_sub_slot: bool
    harvester_id: bytes32


class PostPartialRequest(TypedDict):
    payload: PartialPayload
    aggregate_signature: G2Element


class PostPartialResponse(TypedDict):
    new_difficulty: uint64


class GetFarmerResponse(TypedDict):
    authentication_public_key: G1Element
    payout_instructions: str
    current_difficulty: uint64


class FarmerPayload(TypedDict):
    launcher_id: bytes32
    authentication_token: uint64
    authentication_public_key: NotRequired[G1Element | None]
    payout_instructions: NotRequired[str | None]
    suggested_difficulty: NotRequired[uint64 | None]


class FarmerRequest(TypedDict):
    payload: FarmerPayload
    signature: G2Element


class PostFarmerResponse(TypedDict):
    welcome_message: str


class PutFarmerResponse(TypedDict):
    authentication_public_key: bool | None
    payout_instructions: bool | None
    suggested_difficulty: bool | None


# Collected API
class PoolErrorCode(Enum):
    REVERTED_SIGNAGE_POINT = 1
    TOO_LATE = 2
    NOT_FOUND = 3
    INVALID_PROOF = 4
    PROOF_NOT_GOOD_ENOUGH = 5
    INVALID_DIFFICULTY = 6
    INVALID_SIGNATURE = 7
    SERVER_EXCEPTION = 8
    INVALID_P2_SINGLETON_PUZZLE_HASH = 9
    FARMER_NOT_KNOWN = 10
    FARMER_ALREADY_KNOWN = 11
    INVALID_AUTHENTICATION_TOKEN = 12
    INVALID_PAYOUT_INSTRUCTIONS = 13
    INVALID_SINGLETON = 14
    DELAY_TIME_TOO_SHORT = 15
    REQUEST_FAILED = 16


class ErrorResponse(TypedDict):
    error_code: uint16
    error_message: str | None


ENDPOINTS = [
    APIEndpointMetadata(
        endpoint_name="get_login",
        request_type="GET",
        request=GetRequest,
        response=GetLoginReponse,
    ),
    APIEndpointMetadata(
        endpoint_name="get_farmer",
        request_type="GET",
        request=GetRequest,
        response=GetFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="post_farmer",
        request_type="POST",
        request=FarmerRequest,
        response=PostFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="put_farmer",
        request_type="PUT",
        request=FarmerRequest,
        response=PutFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="get_pool_info",
        request_type="GET",
        request=None,
        response=GetPoolInfoResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="post_partial",
        request_type="POST",
        request=PostPartialRequest,
        response=PostPartialResponse,
    ),
]
