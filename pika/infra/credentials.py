"""Resolve shared credential directories (Hermes-compatible)."""
from __future__ import annotations

import os
from pathlib import Path


def get_credentials_dir() -> Path:
    """Return credential home.

    Resolution order:
    1. ``PIKA_CREDENTIALS_DIR``
    2. ``HERMES_HOME``
    3. ``~/.hermes``
    """
    for key in ("PIKA_CREDENTIALS_DIR", "HERMES_HOME"):
        val = os.environ.get(key, "").strip()
        if val:
            return Path(val).expanduser()
    return Path.home() / ".hermes"


def google_token_path() -> Path:
    return get_credentials_dir() / "google_token.json"


def google_client_secret_path() -> Path:
    return get_credentials_dir() / "google_client_secret.json"


def display_credentials_dir() -> str:
    home = get_credentials_dir()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)
