from __future__ import annotations

from typing import Any, Optional

from agno.agent import Agent
from agno.models.base import Model

from pika.config.loader import get_config
from pika.corrections.store import CorrectionStore
from pika.infra.cache import CacheManager
from pika.infra.db import get_llm_provider
from pika.infra.storage import get_storage
from pika.observability.tracing import get_tracer


class BaseAgent(Agent):
    """
    Extend this to create a pika agent.

    Minimal example:
        class MyAgent(BaseAgent):
            agent_id = 'my_agent'
            description = 'Does X'
            instructions = ['Always be concise', 'Cite sources']
    """

    agent_id: str = ""
    enable_corrections: bool = True
    enable_cache: bool = True

    def __init__(self, **kwargs):
        if not self.agent_id:
            raise ValueError("BaseAgent subclasses must set agent_id")

        cfg = get_config("agents", self.agent_id)
        model: Optional[Model] = kwargs.pop("model", None) or self._resolve_model(cfg)
        enable_corrections = kwargs.pop("enable_corrections", self.enable_corrections)
        enable_cache = kwargs.pop("enable_cache", self.enable_cache)
        db = get_storage()

        agent_kwargs = cfg.get("agent_kwargs", {})
        super().__init__(
            model=model,
            db=db,
            name=self.agent_id,
            **agent_kwargs,
            **kwargs,
        )

        corrections_cfg = cfg.get("corrections", {})
        cache_cfg = cfg.get("cache", {})

        self._cache = CacheManager() if enable_cache and cache_cfg.get("enabled", True) else None
        self._corrections = (
            CorrectionStore(agent_id=self.agent_id)
            if enable_corrections and corrections_cfg.get("enabled", True)
            else None
        )
        self._tracer = get_tracer(self.agent_id)

    def _resolve_model(self, cfg: dict) -> Model:
        provider = cfg.get("llm_provider") or get_config("llm_providers", "default")
        return get_llm_provider(provider)

    async def run(self, message: str, **kwargs) -> Any:
        if self._cache:
            cached = await self._cache.get(self.agent_id, message)
            if cached is not None:
                return cached

        if self._corrections:
            corrections = await self._corrections.retrieve(message)
            if corrections:
                deps = kwargs.setdefault("dependencies", {})
                deps["active_corrections"] = corrections
                kwargs.setdefault("add_dependencies_to_context", True)

        with self._tracer.span("agent.run", input=message):
            result = await super().arun(message, **kwargs)

        if self._cache and result:
            await self._cache.set(self.agent_id, message, result)

        return result
