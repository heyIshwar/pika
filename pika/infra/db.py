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
    if DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres"):
        return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
    raise ValueError(f"Unsupported DATABASE_URL: {DATABASE_URL}")


def get_embedder(name: str = "openai"):
    """Return an Agno Embedder instance by name."""
    if name == "openai":
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        return OpenAIEmbedder()
    if name == "ollama":
        from agno.knowledge.embedder.ollama import OllamaEmbedder

        return OllamaEmbedder()
    if name == "sentence_transformer":
        from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

        return SentenceTransformerEmbedder()
    raise ValueError(f"Unknown embedder: {name!r}. Use 'openai', 'ollama', or 'sentence_transformer'")


def get_vector_store(collection: str = "default", embedder_name: str | None = None):
    """Return an Agno vectordb instance configured via settings.vectordb."""
    from pika.config.loader import get_settings

    cfg = get_settings().get("vectordb", {})
    provider = cfg.get("provider", "lancedb")
    embedder = get_embedder(embedder_name or cfg.get("embedder", "openai"))

    if provider == "lancedb":
        from agno.vectordb.lancedb import LanceDb, SearchType

        return LanceDb(
            uri=cfg.get("path", ".lance"),
            table_name=collection,
            search_type=SearchType.hybrid,
            embedder=embedder,
        )

    if provider == "pgvector":
        from agno.vectordb.pgvector import PgVector

        return PgVector(
            db_url=DATABASE_URL,
            table_name=collection,
            schema=cfg.get("schema", "pika"),
            embedder=embedder,
        )

    raise ValueError(f"Unknown vectordb provider: {provider!r}. Use 'lancedb' or 'pgvector'")


def get_knowledge(collection: str, embedder_name: str | None = None, max_results: int = 10):
    """Return an Agno Knowledge instance backed by the configured vector store."""
    from agno.knowledge.knowledge import Knowledge
    from pika.infra.storage import get_storage

    return Knowledge(
        vector_db=get_vector_store(collection, embedder_name=embedder_name),
        contents_db=get_storage(),
        max_results=max_results,
    )


def get_llm_provider(provider_cfg: dict[str, Any] = {}):
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
    if name == "openrouter":
        from agno.models.openrouter import OpenRouter

        # OpenRouter attribution headers improve rate limits on free models.
        # https://openrouter.ai/docs#request-headers
        extra_headers = {
            "HTTP-Referer": provider_cfg.get("http_referer", "https://pika-agents.dev"),
            "X-Title": provider_cfg.get("app_title", "pika-agents"),
        }

        return OpenRouter(
            id=model,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            extra_headers=extra_headers,
            retries=provider_cfg.get("retries", 2),
            delay_between_retries=provider_cfg.get("delay_between_retries", 5),
            exponential_backoff=provider_cfg.get("exponential_backoff", True),
        )
    if name == "litellm":
        from agno.models.litellm import LiteLLM

        return LiteLLM(id=model)
    raise ValueError(f"Unknown LLM provider: {name}")
