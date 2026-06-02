from __future__ import annotations

from marshmallow import Schema, fields
from rpc import ConfigSchema as RPCConfigSchema


class TXConfigSchema(Schema):
    min_coin_amount = fields.Integer()
    max_coin_amount = fields.Integer()
    excluded_coin_amounts = fields.List(fields.Integer())
    excluded_coin_ids = fields.List(fields.String())
    reuse_puzhash = fields.Boolean()


class ConfigSchema(RPCConfigSchema):
    tx_config = fields.Nested(TXConfigSchema)
