from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, final


@final
@dataclass(frozen=True, kw_only=True)
class APIEndpoint:
    endpoint_name: str
    request_type: Literal["GET", "PUT", "POST"]
    request: type[object] | None
    response: type[object] | None
