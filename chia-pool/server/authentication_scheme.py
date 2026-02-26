# Get the current authentication token according to "Farmer authentication" in SPECIFICATION.md
from __future__ import annotations

import datetime

import jwt
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8


def create_token(*, token_sk: str, plotnft_id: bytes32, expires_minutes: uint8) -> str:
    payload = {
        "sub": plotnft_id.hex(),
        "exp": datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=expires_minutes),
        "iat": datetime.datetime.now(tz=datetime.timezone.utc),
    }
    return jwt.encode(payload, token_sk, algorithm="HS256")


def verify_token(*, token_sk: str, token: str, plotnft_id: bytes32) -> bool:
    return bytes32.from_hexstr(jwt.decode(token, token_sk, algorithms=["HS256"])["sub"]) == plotnft_id
