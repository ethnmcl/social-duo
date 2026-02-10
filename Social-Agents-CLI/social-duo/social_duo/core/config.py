from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from social_duo.core.constraints import DEFAULT_PLATFORM_CONSTRAINTS
from social_duo.types.schemas import AppConfig, PlatformConstraints, PlatformConstraint


def default_config() -> AppConfig:
    constraints = PlatformConstraints(
        x=PlatformConstraint(**DEFAULT_PLATFORM_CONSTRAINTS["x"]),
        linkedin=PlatformConstraint(**DEFAULT_PLATFORM_CONSTRAINTS["linkedin"]),
        instagram=PlatformConstraint(**DEFAULT_PLATFORM_CONSTRAINTS["instagram"]),
        threads=PlatformConstraint(**DEFAULT_PLATFORM_CONSTRAINTS["threads"]),
    )
    return AppConfig(platform_constraints=constraints)


def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text())
    return AppConfig.model_validate(data)


def save_config(path: Path, config: AppConfig) -> None:
    payload = config.model_dump()
    path.write_text(json.dumps(payload, indent=2))


def update_config_value(config: AppConfig, key_path: str, value: str) -> AppConfig:
    # limited dot-path updates
    if key_path.startswith("brand."):
        key_path = key_path.replace("brand.", "brand_voice.", 1)
    data = config.model_dump()
    keys = key_path.split(".")
    cur = data
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            raise ValueError("Invalid config path")
        cur = cur[k]
    cur[keys[-1]] = value
    return AppConfig.model_validate(data)


class ConfigView(BaseModel):
    data: dict
