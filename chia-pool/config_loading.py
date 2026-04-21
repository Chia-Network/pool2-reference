from __future__ import annotations

import pathlib
from typing import TypeVar

import yaml
from marshmallow import Schema

_T_Config = TypeVar("_T_Config")


def canonical_load_config(
    *, root_path: pathlib.Path, config_filename: str, schema_validation: Schema, config_type: type[_T_Config]
) -> _T_Config:
    with root_path.joinpath(config_filename).open(mode="r") as file:
        config_data = yaml.safe_load(file)
        return schema_validation.load(config_data)  # type: ignore[return-type]
