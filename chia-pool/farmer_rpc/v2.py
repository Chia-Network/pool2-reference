from __future__ import annotations

import datetime

from api.farmer_protocols.rest import APIEndpointMetadata, FarmerRPCError, PoolErrorCode
from api.farmer_protocols.v2.farmer import (
    FarmerRequest,
    GetFarmerRequest,
    GetFarmerResponse,
    GetLoginRequest,
    GetLoginResponse,
    GetPoolInfoResponse,
    PartialPayload,
    PostFarmerResponse,
    PostPartialRequest,
    PostPartialResponse,
    PutFarmerResponse,
)
from api.service import Service
from chia_rs import AugSchemeMPL, Program
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint16, uint32, uint64
from farmer_rpc.authentication_scheme import create_token, verify_token
from server.config import Config


async def get_login(request: GetLoginRequest, service: Service, config: Config, token_sk: bytes32) -> GetLoginResponse:
    farmer_record = await service.store.get_farmer(launcher_id=request.launcher_id)
    if farmer_record is None:
        raise FarmerRPCError(
            code=PoolErrorCode.FARMER_NOT_KNOWN, message=f"Farmer with launcher_id {request.launcher_id.hex()} unknown."
        )

    message = (
        bytes(request.timestamp)
        + bytes(request.launcher_id)
        + bytes(service.config["pool_identity"]["pool_claim_hash"], "utf8")
    )
    if not AugSchemeMPL.verify(farmer_record["authentication_public_key"], message, request.signature):
        raise FarmerRPCError(
            code=PoolErrorCode.INVALID_SIGNATURE,
            message=f"Failed to verify signature {request.signature} for launcher_id {request.launcher_id.hex()}.",
        )

    response = await service.store.get_partials(
        launcher_id=request.launcher_id, confirmed=True, since=uint64(service.current_time - 3600)
    )
    return GetLoginResponse(
        recent_partials=response["partials"],
        authentication_token=create_token(
            token_sk=token_sk.hex(),
            plotnft_id=request.launcher_id,
            current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
            expires_minutes=config["authentication_token_timeout"],
        ),
    )


async def get_farmer(
    request: GetFarmerRequest, service: Service, config: Config, token_sk: bytes32
) -> GetFarmerResponse:
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.authentication_token,
        plotnft_id=request.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message=f"Invalid authentication token for launcher_id {request.launcher_id.hex()}.",
        )

    farmer_record = await service.store.get_farmer(launcher_id=request.launcher_id)
    if not farmer_record:
        raise FarmerRPCError(
            code=PoolErrorCode.NOT_FOUND,
            message=f"Farmer with launcher_id {request.launcher_id.hex()} not found.",
        )
    return GetFarmerResponse(
        authentication_public_key=farmer_record["authentication_public_key"],
        payout_instructions=farmer_record["payout_instructions"],
        current_difficulty=farmer_record["difficulty"],
    )


async def post_farmer(
    request: FarmerRequest, service: Service, config: Config, token_sk: bytes32
) -> PostFarmerResponse:
    if (
        request.payload.authentication_public_key is None
        or request.payload.payout_instructions is None
        or request.payload.suggested_difficulty is None
    ):
        raise FarmerRPCError(
            code=PoolErrorCode.REQUEST_FAILED,
            message='Must have "authentication_public_key", "payout_instructions", and "suggested_difficulty" for POST',
        )
    # TODO: verify farmer exists and have the key sign a message
    await service.store.add_farmer(
        version=uint8(2),
        launcher_id=request.payload.launcher_id,
        authentication_public_key=request.payload.authentication_public_key,
        payout_instructions=request.payload.payout_instructions,
        difficulty=request.payload.suggested_difficulty,
    )
    return PostFarmerResponse(welcome_message=config["pool_info"]["welcome_message"])


async def put_farmer(request: FarmerRequest, service: Service, config: Config, token_sk: bytes32) -> PutFarmerResponse:
    if request.authentication_token is None:
        raise FarmerRPCError(
            code=PoolErrorCode.INVALID_AUTHENTICATION_TOKEN, message="Authentication token required for PUT /farmer"
        )
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.authentication_token,
        plotnft_id=request.payload.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message=f"Invalid authentication token for launcher_id {request.payload.launcher_id.hex()}.",
        )
    farmer_record = await service.store.get_farmer(launcher_id=request.payload.launcher_id)
    await service.store.add_farmer(
        version=uint8(2),
        launcher_id=request.payload.launcher_id,
        authentication_public_key=request.payload.authentication_public_key
        if request.payload.authentication_public_key is not None
        else farmer_record["authentication_public_key"],
        payout_instructions=request.payload.payout_instructions
        if request.payload.payout_instructions is not None
        else farmer_record["payout_instructions"],
        difficulty=request.payload.suggested_difficulty
        if request.payload.suggested_difficulty is not None
        else farmer_record["difficulty"],
    )
    return PutFarmerResponse(
        authentication_public_key=request.payload.authentication_public_key is not None,
        payout_instructions=request.payload.payout_instructions is not None,
        suggested_difficulty=request.payload.suggested_difficulty is not None,
    )


async def get_pool_info(  # noqa: RUF029
    request: None,
    service: Service,
    config: Config,
    token_sk: bytes32,
) -> GetPoolInfoResponse:
    # TODO: rate limiting, etc.
    return GetPoolInfoResponse(
        protocol_version=uint8(2),
        name=config["pool_info"]["name"],
        logo_url=config["pool_info"]["logo_url"],
        description=config["pool_info"]["description"],
        minimum_difficulty=config["pool_info"]["minimum_difficulty"],
        fee=uint16(service.config["fee_basis_points"]),
        authentication_token_timeout=config["authentication_token_timeout"],
        relative_lock_height=uint32(service.config["pool_identity"]["relative_lock_height"]),
        target_puzzle_hash=bytes32.from_hexstr(service.config["pool_identity"]["pool_claim_hash"]),
        pool_memoization=Program.fromhex(service.config["pool_identity"]["pool_memoization"]),
    )


def check_partial(*, partial: PartialPayload) -> uint64:
    # TODO: Implement partial check logic
    return uint64(0)


def adjust_difficulty(*, current_difficulty: uint64, partial_difficulty: uint64) -> uint64:
    # TODO: How to do this?
    return uint64(0)


async def post_partial(
    request: PostPartialRequest, service: Service, config: Config, token_sk: bytes32
) -> PostPartialResponse:
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.authentication_token,
        plotnft_id=request.payload.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message=f"Invalid authentication token for launcher_id {request.payload.launcher_id.hex()}.",
        )
    farmer = await service.store.get_farmer(launcher_id=request.payload.launcher_id)
    partial_difficulty = check_partial(partial=request.payload)
    await service.store.add_partial(
        launcher_id=request.payload.launcher_id,
        timestamp=service.current_time,
        difficulty=partial_difficulty,
    )
    return PostPartialResponse(
        new_difficulty=adjust_difficulty(
            current_difficulty=farmer["difficulty"], partial_difficulty=partial_difficulty
        ),
    )


METADATA = [
    APIEndpointMetadata(
        endpoint_name="get_login",
        request_type="GET",
        request=GetLoginRequest,
        response=GetLoginResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="get_farmer",
        request_type="GET",
        request=GetFarmerRequest,
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
HANDLERS = {
    "get_login": get_login,
    "get_farmer": get_farmer,
    "post_farmer": post_farmer,
    "put_farmer": put_farmer,
    "get_pool_info": get_pool_info,
    "post_partial": post_partial,
}
