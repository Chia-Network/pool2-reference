from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from chia_rs.sized_ints import uint8, uint16, uint64
from marshmallow import Schema, ValidationError, fields, validates
from typing_extensions import TypedDict

CONFIG_FILE_NAME = "pool_server_config.yaml"


class LoggingConfigSchema(Schema):
    log_level = fields.Str(required=True)
    log_stdout = fields.Bool(required=True)
    log_syslog = fields.Bool(required=True)
    log_syslog_host = fields.Str(required=True)
    log_syslog_port = fields.Int(required=True)
    log_filename = fields.Str(required=True)
    log_maxfilesrotation = fields.Int(required=True)
    log_max_bytes_rotation = fields.Int(required=True)
    log_use_gzip = fields.Bool(required=True)

    @validates("log_level")
    def validate_log_level(self, value: str, data_key: str) -> None:
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValidationError("Invalid log level")


class PoolInfoConfigSchema(Schema):
    name = fields.Str(required=True)
    log_url = fields.URL(required=True)
    description = fields.Str(required=True)
    welcome_message = fields.Str(required=True)


class WebConfigSchema(Schema):
    host = fields.Str(required=True)
    port = fields.Int(required=True)
    ssl_cert_path = fields.Str(required=True)
    ssl_key_path = fields.Str(required=True)


class ConfigSchema(Schema):
    logging = fields.Nested(LoggingConfigSchema)
    pool_info = fields.Nested(PoolInfoConfigSchema)
    web_config = fields.Nested(WebConfigSchema)
    service_loop_intervals = fields.Int(required=True)
    authentication_token_timeout = fields.Int(required=True)


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


class WebConfig(TypedDict):
    host: str
    port: int
    ssl_cert_path: str
    ssl_key_path: str


class Config(TypedDict):
    logging: LoggingConfig
    pool_info: PoolInfoConfig
    service_loop_intervals: uint8
    web_config: WebConfig
    authentication_token_timeout: uint8


def load(data: Config) -> Config:
    ConfigSchema().load(data)
    return data


def canonical_load_config() -> Config:
    with Path.home().joinpath(CONFIG_FILE_NAME).open(mode="r") as file:
        config_data = yaml.safe_load(file)
    return Config(config_data)
