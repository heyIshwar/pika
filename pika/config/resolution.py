"""Config root resolution for library-safe usage."""
from __future__ import annotations

import os
import pathlib

_BUNDLED_CONFIG = pathlib.Path(__file__).resolve().parents[2] / "config"
_last_cwd: str = ""


def resolve_config_root() -> pathlib.Path:
    """
    Return the config directory to use.

    Resolution order:
    1. $PIKA_CONFIG_DIR env var
    2. CWD/config/ directory (multi-file, current pika style)
    3. Pika package's bundled config/ (fallback defaults)

    A CWD/pika.yaml flat file is handled separately in loader.py.
    """
    global _last_cwd
    _last_cwd = os.getcwd()

    explicit = os.getenv("PIKA_CONFIG_DIR")
    if explicit:
        p = pathlib.Path(explicit)
        if p.is_dir():
            return p

    cwd_config = pathlib.Path(os.getcwd()) / "config"
    if cwd_config.is_dir():
        return cwd_config

    return _BUNDLED_CONFIG


def cwd_changed() -> bool:
    """True if working directory has changed since last resolution."""
    return os.getcwd() != _last_cwd


def flat_config_path() -> pathlib.Path | None:
    """Return CWD/pika.yaml if it exists (flat single-file SDK config)."""
    p = pathlib.Path(os.getcwd()) / "pika.yaml"
    return p if p.exists() else None
