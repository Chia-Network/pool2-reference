from __future__ import annotations

import pathlib

from marshmallow import Schema, fields, validates
from typing_extensions import TypedDict

CONFIG_FILE_NAME = "pool_sql_store_config.yaml"


class ConfigSchema(Schema):
    store_path = fields.Str(required=True)

    @validates("store_path")
    def validate_store_path(self, value: str, data_key: str) -> None:
        if not pathlib.Path(value).exists():
            pathlib.Path(value).touch()


class Config(TypedDict):
    store_path: str


def load(data: Config) -> Config:
    ConfigSchema().load(data)
    return data
