from __future__ import annotations

import asyncio
import datetime

from api.node import FullNode
from api.service import Service, ServiceConfig
from api.store import GetFarmerResponse, PartialMetadata, Store
from chia.consensus.default_constants import DEFAULT_CONSTANTS
from chia.consensus.pot_iterations import calculate_iterations_quality
from chia.farmer.authentication import create_token, verify_token
from chia.pools.plotnft_drivers import RewardPuzzle
from chia.protocols import pool_protocol
from chia.types.blockchain_format.proof_of_space import verify_and_get_quality_string
from chia_rs import AugSchemeMPL, G2Element, Program
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
    if request.payload.authentication_public_key is None or request.payload.payout_instructions is None:
        raise FarmerRPCError(
            code=pool_protocol.PoolErrorCode.REQUEST_FAILED,
            message='Must have "authentication_public_key" and "payout_instructions" for POST',
        )
    # TODO: verify farmer exists and have the key sign a message
    await service.store.add_farmer(
        version=uint8(2),
        launcher_id=request.payload.launcher_id,
        authentication_public_key=request.payload.authentication_public_key,
        payout_instructions=request.payload.payout_instructions,
        difficulty=uint64(service.config["default_difficulty"])
        if request.payload.suggested_difficulty is None
        else request.payload.suggested_difficulty,
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
        minimum_difficulty=uint64(service.config["min_difficulty"]),
        fee=str(uint16(service.config["fee_basis_points"])),
        authentication_token_timeout=config["authentication_token_timeout"],
        relative_lock_height=uint32(service.config["pool_identity"]["relative_lock_height"]),
        target_puzzle_hash=bytes32.from_hexstr(service.config["pool_identity"]["pool_claim_hash"]),
        pool_memoization=Program.fromhex(service.config["pool_identity"]["pool_memoization"]),
    )


async def check_partial(
    *,
    partial: pool_protocol.PostPartialPayload,
    node_rpc_client: FullNode,
    agg_sig: G2Element,
    farmer_record: GetFarmerResponse,
    launcher_id: bytes32,
    current_time: uint64,
    service_config: ServiceConfig,
    store: Store,
) -> None:
    message: bytes32 = partial.get_hash()
    if not AugSchemeMPL.aggregate_verify(
        [partial.proof_of_space.plot_public_key, farmer_record["authentication_public_key"]],
        [message, message],
        agg_sig,
    ):
        raise FarmerRPCError(pool_protocol.PoolErrorCode.INVALID_SIGNATURE, "The aggregate signature is invalid")

    if partial.proof_of_space.pool_contract_puzzle_hash != RewardPuzzle(singleton_id=launcher_id).puzzle_hash():
        raise FarmerRPCError(
            pool_protocol.PoolErrorCode.INVALID_P2_SINGLETON_PUZZLE_HASH,
            f"Invalid pool contract puzzle hash {partial.proof_of_space.pool_contract_puzzle_hash}",
        )

    recent = None
    for _ in range(2):
        if partial.end_of_sub_slot:
            recent = await node_rpc_client.get_recent_end_of_subslot(challenge_hash=partial.sp_hash)
        else:
            recent = await node_rpc_client.get_recent_signage_point(signage_point_hash=partial.sp_hash)
        if recent["exists"]:
            break
        await asyncio.sleep(10)  # TODO: configurable

    if recent is None or not recent["exists"] or recent["reverted"]:
        raise FarmerRPCError(
            pool_protocol.PoolErrorCode.NOT_FOUND, f"Did not find signage point or EOS {partial.sp_hash}"
        )

    if current_time - recent["time_received"] > service_config["partial_time_limit"]:
        raise FarmerRPCError(
            pool_protocol.PoolErrorCode.TOO_LATE,
            f"Received partial in {current_time - recent['time_received']}. "
            f"Make sure your proof of space lookups are fast, and network connectivity is good."
            f"Response must happen in less than {service_config['partial_time_limit']} seconds. NAS or network"
            f" farming can be an issue",
        )

    # Validate the proof
    if recent["signage_point"] is not None:
        assert recent["signage_point"].cc_vdf
        challenge_hash: bytes32 = recent["signage_point"].cc_vdf.challenge
    elif recent["eos"] is not None:
        assert recent["eos"].challenge_chain
        challenge_hash = recent["eos"].challenge_chain.get_hash()
    else:
        raise RuntimeWarning("semantically impossible: both signage_point and eos are None")  # pragma: no cover

    # Note the use of peak_height + 1. We Are evaluating the suitability for the next block
    constants = DEFAULT_CONSTANTS  # TODO: get constants via node or something
    blockchain_state = await node_rpc_client.get_blockchain_state()
    quality_string = verify_and_get_quality_string(
        partial.proof_of_space,
        constants,
        challenge_hash,
        partial.sp_hash,
        height=uint32(blockchain_state["peak"] + 1),
        prev_transaction_block_height=uint32(0),  # TODO
    )
    if quality_string is None:
        raise FarmerRPCError(
            pool_protocol.PoolErrorCode.INVALID_PROOF,
            f"Invalid proof of space {partial.sp_hash}",
        )

    required_iters = calculate_iterations_quality(
        constants,
        quality_string,
        partial.proof_of_space.param(),
        farmer_record["difficulty"],
        partial.sp_hash,
    )

    if required_iters >= constants.POOL_SUB_SLOT_ITERS // 64:
        raise FarmerRPCError(
            pool_protocol.PoolErrorCode.PROOF_NOT_GOOD_ENOUGH,
            f"Proof of space has required iters {required_iters}, "
            f"too high for difficulty {farmer_record['difficulty']}",
        )

    await store.add_partial(
        launcher_id=launcher_id,
        partial=PartialMetadata(
            timestamp=current_time,
            difficulty=required_iters,
            challenge_hash=partial.sp_hash,
            pos_hash=partial.proof_of_space.get_hash(),
            end_of_sub_slot=partial.end_of_sub_slot,
            # this was checked above to match the farmer's pool_contract_puzzle_hash
            pool_contract_puzzle_hash=partial.proof_of_space.pool_contract_puzzle_hash,  # type: ignore[arg-type]
        ),
    )


async def adjust_difficulty(
    *,
    launcher_id: bytes32,
    service_config: ServiceConfig,
    current_difficulty: uint64,
    current_time: uint64,
    store: Store,
) -> uint64:
    recent_partials = (
        await store.get_partials(
            launcher_id=launcher_id, confirmed=True, count=uint64(service_config["number_of_partials_target"])
        )
    )["partials"]
    # If we haven't processed any partials yet, maintain the current (default) difficulty
    if len(recent_partials) < 2:  # noqa: PLR2004
        return current_difficulty

    # If we recently updated difficulty, don't update again
    if any(recent_partial.difficulty != current_difficulty for recent_partial in recent_partials):
        return current_difficulty

    # Lower the difficulty if we are really slow since our last partial
    ONE_HOUR = 3600
    if current_time - recent_partials[0].timestamp > 3 * ONE_HOUR:
        return uint64(max(service_config["min_difficulty"], current_difficulty // 5))

    if current_time - recent_partials[0].timestamp > ONE_HOUR:
        return uint64(max(service_config["min_difficulty"], uint64(int(current_difficulty // 1.5))))

    time_taken = (recent_partials[0].timestamp - recent_partials[-1].timestamp) * 1.0

    # If we don't have enough partials at this difficulty and time between last and
    # 1st partials is below target time, don't update yet
    if (
        len(recent_partials) < service_config["number_of_partials_target"]
        and time_taken < service_config["time_target"]
    ):
        return current_difficulty

    # Adjust time_taken if number of partials didn't reach number_of_partials_target
    if len(recent_partials) < service_config["number_of_partials_target"]:
        time_taken = time_taken * service_config["number_of_partials_target"] / len(recent_partials)

    # Finally, this is the standard case of normal farming and slow (or no) growth, adjust to the new difficulty
    new_difficulty = uint64(int(current_difficulty * service_config["time_target"] / time_taken))
    return uint64(max(service_config["min_difficulty"], new_difficulty))


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
    await check_partial(
        partial=request.payload,
        node_rpc_client=service.full_node,
        agg_sig=request.aggregate_signature,
        farmer_record=farmer,
        launcher_id=request.payload.launcher_id,
        current_time=service.current_time,
        service_config=service.config,
        store=service.store,
    )
    new_difficulty = await adjust_difficulty(
        launcher_id=request.payload.launcher_id,
        current_difficulty=farmer["difficulty"],
        current_time=service.current_time,
        service_config=service.config,
        store=service.store,
    )
    await service.store.add_farmer(
        version=farmer["version"],
        launcher_id=request.payload.launcher_id,
        payout_instructions=farmer["payout_instructions"],
        difficulty=new_difficulty,
        authentication_public_key=farmer["authentication_public_key"],
    )
    return pool_protocol.PostPartialResponse(
        new_difficulty=new_difficulty,
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
