from __future__ import annotations

import datetime

from api.service import Service
from chia.farmer.authentication import create_token, verify_token
from chia.protocols import pool_protocol
from chia_rs import AugSchemeMPL, Program
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint16, uint32, uint64
from farmer_rpc.api import APIEndpointMetadata, FarmerRPCError
from server.config import Config


async def get_auth(
    request: pool_protocol.GetAuthRequest, service: Service, config: Config, token_sk: bytes32
) -> pool_protocol.GetAuthResponse:
    """
    This endpoint can be called by an existing farmer to obtain an authentication token to be used with many of the
    other endpoints.

    In order to prove that the farmer is who they claim to be, the farmer must sign a message with the key that controls
    exiting from the pool.
    """
    farmer_record = await service.store.get_farmer(launcher_id=request.payload.launcher_id)
    if farmer_record is None:
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.FARMER_NOT_KNOWN,
            message=f"Farmer with launcher_id {request.payload.launcher_id.hex()} unknown.",
        )

    message = (
        bytes(request.payload.timestamp)
        + bytes(request.payload.launcher_id)
        + bytes(service.config["pool_identity"]["pool_claim_hash"], "utf8")
    )
    if not AugSchemeMPL.verify(farmer_record["authentication_public_key"], message, request.signature):
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.INVALID_SIGNATURE,
            message=(
                f"Failed to verify signature {request.signature} for launcher_id {request.payload.launcher_id.hex()}."
            ),
        )

    return pool_protocol.GetAuthResponse(
        authentication_token=create_token(
            token_sk=token_sk.hex(),
            plotnft_id=request.payload.launcher_id,
            current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
            expires_minutes=config["authentication_token_timeout"],
        ),
    )


async def get_farmer(
    request: pool_protocol.GetFarmerRequest, service: Service, config: Config, token_sk: bytes32
) -> pool_protocol.GetFarmerResponse:
    """
    This endpoint requires an authentication token.

    Returns all of the relevant information about a given farmer that the pool has.
    """
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.authentication_token_v2,
        plotnft_id=request.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message=f"Invalid authentication token for launcher_id {request.launcher_id.hex()}.",
        )

    farmer_record = await service.store.get_farmer(launcher_id=request.launcher_id)
    if not farmer_record:
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.NOT_FOUND,
            message=f"Farmer with launcher_id {request.launcher_id.hex()} not found.",
        )
    return pool_protocol.GetFarmerResponse(
        authentication_public_key=farmer_record["authentication_public_key"],
        payout_instructions=farmer_record["payout_instructions"],
        current_difficulty=farmer_record["difficulty"],
        current_points=uint64(0),  # TODO
    )


async def post_farmer(
    request: pool_protocol.PostFarmerRequest, service: Service, config: Config, token_sk: bytes32
) -> pool_protocol.PostFarmerResponse:
    """
    This endpoint may be called by anybody to add a new farmer to the pool.

    The farmer must prove that they exist and that they control the pooling singleton by signing a message with the key
    that controls exiting from the pool.
    """
    if (
        request.payload.authentication_public_key is None
        or request.payload.payout_instructions is None
        or request.payload.suggested_difficulty is None
    ):
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.REQUEST_FAILED,
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
    return pool_protocol.PostFarmerResponse(welcome_message=config["pool_info"]["welcome_message"])


async def put_farmer(
    request: pool_protocol.PutFarmerRequest, service: Service, config: Config, token_sk: bytes32
) -> pool_protocol.PutFarmerResponse:
    """
    This endpoint requires an authentication token.

    The purpose of this endpoint is to update any farmer information after the farmer has already been posted.
    """
    if request.payload.authentication_token is None:
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message="Authentication token required for PUT /farmer",
        )
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.payload.authentication_token_v2,
        plotnft_id=request.payload.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
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
    return pool_protocol.PutFarmerResponse(
        authentication_public_key=request.payload.authentication_public_key is not None,
        payout_instructions=request.payload.payout_instructions is not None,
        suggested_difficulty=request.payload.suggested_difficulty is not None,
    )


async def get_pool_info(  # noqa: RUF029
    request: None,
    service: Service,
    config: Config,
    token_sk: bytes32,
) -> pool_protocol.GetPoolInfoResponse:
    """
    The endpoint requires no authentication and can basically be used as the index.html for information about the pool.
    """
    # TODO: rate limiting, etc.
    return pool_protocol.GetPoolInfoResponse(
        protocol_version=uint8(2),
        name=config["pool_info"]["name"],
        logo_url=config["pool_info"]["logo_url"],
        description=config["pool_info"]["description"],
        minimum_difficulty=config["pool_info"]["minimum_difficulty"],
        fee=str(uint16(service.config["fee_basis_points"])),
        authentication_token_timeout=config["authentication_token_timeout"],
        relative_lock_height=uint32(service.config["pool_identity"]["relative_lock_height"]),
        target_puzzle_hash=bytes32.from_hexstr(service.config["pool_identity"]["pool_claim_hash"]),
        pool_memoization=Program.fromhex(service.config["pool_identity"]["pool_memoization"]),
    )


def check_partial(*, partial: pool_protocol.PostPartialPayload) -> uint64:
    # TODO: Implement partial check logic
    return uint64(0)


def adjust_difficulty(*, current_difficulty: uint64, partial_difficulty: uint64) -> uint64:
    # TODO: How to do this?
    return uint64(0)


async def post_partial(
    request: pool_protocol.PostPartialRequest, service: Service, config: Config, token_sk: bytes32
) -> pool_protocol.PostPartialResponse:
    """
    This endpoint requires an authentication token.

    The purpose of this endpoint is to submit a partial to the pool which the pool will confirm and in turn credit
    the farmer so they receive payouts proportional to the work they are doing for the pool.
    """
    if not verify_token(
        token_sk=token_sk.hex(),
        token=request.authentication_token_v2,
        plotnft_id=request.payload.launcher_id,
        current_time=datetime.datetime.fromtimestamp(service.current_time, tz=datetime.timezone.utc),
    ):
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.INVALID_AUTHENTICATION_TOKEN,
            message=f"Invalid authentication token for launcher_id {request.payload.launcher_id.hex()}.",
        )
    farmer = await service.store.get_farmer(launcher_id=request.payload.launcher_id)
    partial_difficulty = check_partial(partial=request.payload)
    await service.store.add_partial(
        launcher_id=request.payload.launcher_id,
        timestamp=service.current_time,
        difficulty=partial_difficulty,
    )
    return pool_protocol.PostPartialResponse(
        new_difficulty=adjust_difficulty(
            current_difficulty=farmer["difficulty"], partial_difficulty=partial_difficulty
        ),
    )


METADATA = [
    APIEndpointMetadata(
        endpoint_name="get_auth",
        request_type="GET",
        request=pool_protocol.AuthenticationPayloadV2,
        response=pool_protocol.GetAuthResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="get_farmer",
        request_type="GET",
        request=pool_protocol.GetFarmerRequest,
        response=pool_protocol.GetFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="post_farmer",
        request_type="POST",
        request=pool_protocol.PostFarmerRequest,
        response=pool_protocol.PostFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="put_farmer",
        request_type="PUT",
        request=pool_protocol.PutFarmerRequest,
        response=pool_protocol.PutFarmerResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="get_pool_info",
        request_type="GET",
        request=None,
        response=pool_protocol.GetPoolInfoResponse,
    ),
    APIEndpointMetadata(
        endpoint_name="post_partial",
        request_type="POST",
        request=pool_protocol.PostPartialRequest,
        response=pool_protocol.PostPartialResponse,
    ),
]
HANDLERS = {
    "get_auth": get_auth,
    "get_farmer": get_farmer,
    "post_farmer": post_farmer,
    "put_farmer": put_farmer,
    "get_pool_info": get_pool_info,
    "post_partial": post_partial,
}
