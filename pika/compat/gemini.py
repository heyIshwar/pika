"""Workaround for Gemini-via-OpenRouter tool-name namespace prefix bug.

Some Gemini models through OpenRouter's OpenAI-compatible endpoint prefix
function-call names with a namespace segment (e.g. `default_api.search`).
Agno's function lookup is exact-match, so prefixed names fail silently.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("pika.compat.gemini")

_installed = False


def install() -> None:
    """Idempotent — safe to call from app startup or CLI entry points."""
    global _installed
    if _installed:
        return

    import agno.utils.functions as functions_mod
    import agno.utils.tools as tools_mod

    original = functions_mod.get_function_call

    def patched(name, arguments=None, call_id=None, functions=None):
        if functions and name not in functions and "." in name:
            unprefixed = name.split(".", 1)[1]
            if unprefixed in functions:
                logger.warning(
                    "stripping namespace prefix from tool call %r -> %r",
                    name,
                    unprefixed,
                )
                name = unprefixed
        return original(name, arguments=arguments, call_id=call_id, functions=functions)

    functions_mod.get_function_call = patched
    tools_mod.get_function_call = patched

    _installed = True
