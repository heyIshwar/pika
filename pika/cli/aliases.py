"""In-package command aliases for `pika chu` and `pika choo` (not shell aliases)."""

from __future__ import annotations

# canonical subcommand -> extra `pika <name>` aliases
COMMAND_ALIASES: dict[str, list[str]] = {
    "chu": ["pikachu"],
    "choo": ["pikachoo"],
}

# standalone console_scripts -> canonical subcommand
ENTRYPOINT_ALIASES: dict[str, str] = {
    "pikachu": "chu",
    "pika-chu": "chu",
    "pikachoo": "choo",
    "pika-choo": "choo",
}


def interactive_command_names(canonical: str) -> list[str]:
    """Canonical name plus all in-package aliases."""
    return [canonical, *COMMAND_ALIASES.get(canonical, [])]


def chu_app() -> None:
    """Standalone entrypoint for pikachu / pika-chu."""
    from pika.cli.main import chu_main

    chu_main()


def choo_app() -> None:
    """Standalone entrypoint for pikachoo / pika-choo."""
    from pika.cli.main import choo_main

    choo_main()
