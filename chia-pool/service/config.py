from __future__ import annotations

from chia_rs import Program
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32, uint64
from typing_extensions import TypedDict


class PoolIdentityConfig(TypedDict):
    relative_lock_height: uint32
    pool_claim_hash: bytes32
    pool_memoization: Program


class ServiceConfig(TypedDict):
    pool_identity: PoolIdentityConfig
    min_difficulty: uint64
    default_difficulty: uint64
    partial_time_limit: uint64
    partial_confirmation_delay: uint64
    scan_start_height: uint32
    collect_pool_rewards_interval: uint64
    confirmation_security_threshold: uint32
    payment_interval: uint64
    max_additions_per_transaction: uint32
    number_of_partials_target: uint32
    time_target: uint64
