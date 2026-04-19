from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validates


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
    logo_url = fields.URL(required=True)
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
