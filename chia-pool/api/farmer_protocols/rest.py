from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, final

from chia.util.streamable import Streamable, streamable
from chia_rs.sized_ints import uint16


@final
@dataclass(frozen=True, kw_only=True)
class APIEndpointMetadata:
    endpoint_name: str
    request_type: Literal["GET", "PUT", "POST"]
    request: type[Streamable] | None
    response: type[Streamable] | None


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


@streamable
@dataclass(frozen=True, kw_only=True)
class ErrorResponse(Streamable):
    error_code: uint16
    error_message: str | None


class FarmerRPCError(Exception):
    code: PoolErrorCode
    message: str

    def __init__(self, code: PoolErrorCode, message: str) -> None:
        self.code = code
        self.message = message
