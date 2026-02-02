from __future__ import annotations

from typing import Literal

from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint8, uint16, uint32, uint64
from typing_extensions import TypedDict


class LoggingConfig(TypedDict):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    log_stdout: bool
    log_syslog: bool
    log_syslog_host: str
    log_syslog_port: uint16
    log_filename: str
    log_maxfilesrotation: uint8
    log_max_bytes_rotation: uint64
    log_use_gzip: bool


class PoolInfoConfig(TypedDict):
    name: str
    log_url: str
    description: str
    welcome_message: str


class PoolIdentityConfig(TypedDict):
    relative_lock_height: uint32
    pool_claim_hash: bytes32


class Config(TypedDict):
    logging: LoggingConfig
    pool_info: PoolInfoConfig
    pool_identity: PoolIdentityConfig
    min_difficulty: uint64
    default_difficulty: uint64
    authentication_token_timeout: uint8
    partial_time_limit: uint64
    partial_confirmation_delay: uint64
    scan_start_height: uint32
    collect_pool_rewards_interval: uint64
    confirmation_security_threshold: uint32
    payment_interval: uint64
    max_additions_per_transaction: uint32
    number_of_partials_target: uint32
    time_target: uint64
