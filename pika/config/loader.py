from __future__ import annotations

import yaml
import pathlib
from functools import lru_cache
from typing import TYPE_CHECKING

from pika.config.resolution import resolve_config_root, cwd_changed, flat_config_path

if TYPE_CHECKING:
    from pika.core.agent import BaseAgent
    from pika.core.team import BaseTeam

Runner = "BaseAgent | BaseTeam"


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _bust_cache_if_needed():
    """Clear LRU caches when CWD changed (important for library use)."""
    if cwd_changed():
        get_config.cache_clear()
        get_settings.cache_clear()


@lru_cache(maxsize=None)
def get_config(section: str, key: str) -> dict:
    """
    Load config for a section/key pair.

    Resolution order (per resolve_config_root):
    1. $PIKA_CONFIG_DIR/<section>/<key>.yaml
    2. CWD/config/<section>/<key>.yaml
    3. Bundled pika/config/<section>/<key>.yaml

    Then overlays CWD/config/overrides/<section>/<key>.yaml if present.
    """
    _bust_cache_if_needed()
    base_dir = resolve_config_root()
    override_dir = base_dir / "overrides"

    base_path = base_dir / section / f"{key}.yaml"
    override_path = override_dir / section / f"{key}.yaml"

    base: dict = {}
    if base_path.exists():
        base = yaml.safe_load(base_path.read_text()) or {}

    if override_path.exists():
        override = yaml.safe_load(override_path.read_text()) or {}
        base = _deep_merge(base, override)

    return base


@lru_cache(maxsize=1)
def get_settings() -> dict:
    """
    Return global pika settings.

    Checks CWD/pika.yaml (flat SDK config) first, then config/settings.yaml.
    The flat pika.yaml must have a top-level 'pika:' key.
    """
    _bust_cache_if_needed()

    flat = flat_config_path()
    if flat:
        data = yaml.safe_load(flat.read_text()) or {}
        return data.get("pika", data)

    settings_path = resolve_config_root() / "settings.yaml"
    if not settings_path.exists():
        return {}
    return yaml.safe_load(settings_path.read_text()) or {}


def get_validated_settings():
    """Return settings validated against PikaSettings schema."""
    from pika.config.schema import PikaSettings

    return PikaSettings.model_validate(get_settings())
