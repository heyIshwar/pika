import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pika.db")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    if DATABASE_URL.startswith("mysql"):
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    raise ValueError(f"Unsupported DATABASE_URL: {DATABASE_URL}")


def get_llm_provider(provider_cfg: dict[str, Any]):
    """Return Agno model instance for a provider config dict."""
    name = provider_cfg.get("name", "openai")
    model = provider_cfg.get("model", "gpt-4o-mini")

    if name == "openai":
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=model)
    if name == "anthropic":
        from agno.models.anthropic import Claude

        return Claude(id=model)
    if name == "groq":
        from agno.models.groq import Groq

        return Groq(id=model)
    if name == "ollama":
        from agno.models.ollama import Ollama

        return Ollama(id=model)
    raise ValueError(f"Unknown LLM provider: {name}")
