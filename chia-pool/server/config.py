from __future__ import annotations

from typing import Literal

from chia_rs.sized_ints import uint8, uint16, uint64
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


class Config(TypedDict):
    logging: LoggingConfig
    pool_info: PoolInfoConfig
    authentication_token_timeout: uint8
