from __future__ import annotations

from dataclasses import dataclass

from chia.types.blockchain_format.program import Program
from chia_rs.sized_bytes import bytes32
from marshmallow import Schema, ValidationError, fields, validates
from marshmallow.validate import Validator


@dataclass(frozen=True, kw_only=True)
class UIntValidator(Validator):
    num_bits: int

    def __call__(self, value: int) -> bool:
        return value >= 0 and value.bit_length() <= self.num_bits


class PoolIdentitySchema(Schema):
    relative_lock_height = fields.Integer(required=True, validate=UIntValidator(num_bits=32))
    pool_claim_hash = fields.String(required=True)
    pool_memoization = fields.String(required=True)

    @validates("pool_claim_hash")
    def validate_pool_claim_hash(self, value: str, data_key: str) -> None:
        try:
            bytes32.from_hexstr(value)
        except Exception as err:
            raise ValidationError("Pool claim hash must be a valid hex string") from err

    @validates("pool_memoization")
    def validate_pool_memoization(self, value: str, data_key: str) -> None:
        try:
            Program.fromhex(value)
        except Exception as err:
            raise ValidationError("Pool memoization must be a valid hex string") from err


class ConfigSchema(Schema):
    pool_identity = fields.Nested(PoolIdentitySchema)
    min_difficulty = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    default_difficulty = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    partial_time_limit = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    partial_confirmation_delay = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    scan_start_height = fields.Integer(required=True, validate=UIntValidator(num_bits=32))
    confirmation_security_threshold = fields.Integer(required=True, validate=UIntValidator(num_bits=32))
    max_additions_per_transaction = fields.Integer(required=True, validate=UIntValidator(num_bits=32))
    number_of_partials_target = fields.Integer(required=True, validate=UIntValidator(num_bits=32))
    time_target = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    fee_basis_points = fields.Integer(required=True, validate=UIntValidator(num_bits=64))
    genesis_challenge = fields.Str(required=True)
