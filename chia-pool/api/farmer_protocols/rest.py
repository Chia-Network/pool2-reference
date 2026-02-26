from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, final

from chia.util.streamable import Streamable


@final
@dataclass(frozen=True, kw_only=True)
class APIEndpointMetadata:
    endpoint_name: str
    request_type: Literal["GET", "PUT", "POST"]
    request: type[Streamable] | None
    response: type[Streamable] | None
