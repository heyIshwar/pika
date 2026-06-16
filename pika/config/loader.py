from __future__ import annotations

import yaml
import pathlib
from functools import lru_cache

BASE_DIR = pathlib.Path(__file__).resolve().parents[2] / "config"
OVERRIDE_DIR = BASE_DIR / "overrides"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@lru_cache(maxsize=None)
def get_config(section: str, key: str) -> dict:
    """
    Load config for a section/key pair.

    Resolution order:
    1. config/<section>/<key>.yaml
    2. config/overrides/<section>/<key>.yaml (wins on collision)
    """
    base_path = BASE_DIR / section / f"{key}.yaml"
    override_path = OVERRIDE_DIR / section / f"{key}.yaml"

    base: dict = {}
    if base_path.exists():
        base = yaml.safe_load(base_path.read_text()) or {}

    if override_path.exists():
        override = yaml.safe_load(override_path.read_text()) or {}
        base = _deep_merge(base, override)

    return base
