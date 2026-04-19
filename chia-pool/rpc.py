from __future__ import annotations

from marshmallow import Schema, fields


class SSLSchema(Schema):
    private_crt = fields.Str(required=True)
    private_key = fields.Str(required=True)


class PrivateSSLSchema(Schema):
    crt = fields.Str(required=True)
    key = fields.Str(required=True)


class NetConfigSchema(Schema):
    rpc_timeout = fields.Int(required=True)
    daemon_ssl = fields.Nested(SSLSchema, required=True)
    private_ssl_ca = fields.Nested(PrivateSSLSchema, required=True)


class ConfigSchema(Schema):
    self_hostname = fields.Str(required=True)
    rpc_port = fields.Int(required=True)
    root_path = fields.Str(required=True)
    net_config = fields.Nested(NetConfigSchema, required=True)
