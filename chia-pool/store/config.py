from __future__ import annotations

import pathlib

from marshmallow import Schema, fields, validates


class ConfigSchema(Schema):
    store_path = fields.Str(required=True)

    @validates("store_path")
    def validate_store_path(self, value: str, data_key: str) -> None:
        if not pathlib.Path(value).exists():
            pathlib.Path(value).touch()
