from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional

from agno.agent import Agent
from agno.models.base import Model

from pika.config.loader import get_config, get_settings
from pika.corrections.store import CorrectionStore
from pika.infra.cache import CacheManager
from pika.infra.db import get_llm_provider
from pika.infra.storage import get_storage
from pika.observability.model import SpanKind
from pika.observability.tracing import get_tracer
from pika.core.states import AgentState


class BaseAgent(Agent):
    """
    Extend this to create a pika agent.

    Minimal example:
        class MyAgent(BaseAgent):
            agent_id = 'my_agent'
            description = 'Does X'
            instructions = ['Always be concise', 'Cite sources']

    To enable memory (stored/recalled across sessions via Agno MemoryManager):
        # In config/agents/my_agent.yaml:
        memory:
          enabled: true
          enable_user_memories: true
          add_to_context: true

    To attach skills (reusable tool bundles):
        class MyAgent(BaseAgent):
            skills = [WebSearchSkill()]
    """

    agent_id: str = ""
    enable_corrections: bool = True
    enable_cache: bool = True
    skills: List = []  # list[BaseSkill]

    def __init__(self, **kwargs):
        if not self.agent_id:
            raise ValueError("BaseAgent subclasses must set agent_id")

        cfg = get_config("agents", self.agent_id)
        db = get_storage()
        model: Optional[Model] = kwargs.pop("model", None) or self._resolve_model(cfg)

        enable_corrections = kwargs.pop("enable_corrections", self.enable_corrections)
        enable_cache = kwargs.pop("enable_cache", self.enable_cache)

        # --- Memory (Agno MemoryManager) ---
        memory_cfg = cfg.get("memory", {})
        memory_manager = None
        if memory_cfg.get("enabled", False):
            from agno.memory.manager import MemoryManager

            memory_manager = MemoryManager(model=model, db=db)

        # --- Knowledge ---
        knowledge = None
        knowledge_cfg = cfg.get("knowledge")
        if knowledge_cfg:
            knowledge = self._build_knowledge(knowledge_cfg)

        # --- Skills → Agno Toolkits ---
        skill_toolkits = [s.as_toolkit() for s in (self.__class__.skills or [])]

        # --- Merge Agno kwargs: global settings < per-agent config < call-time kwargs ---
        agno_global = get_settings().get("agno", {})
        agent_kwargs: dict = {**agno_global, **cfg.get("agent_kwargs", {})}

        # Memory options forwarded to Agno
        if memory_manager is not None:
            agent_kwargs["memory_manager"] = memory_manager
            agent_kwargs["enable_user_memories"] = memory_cfg.get("enable_user_memories", True)
            agent_kwargs["add_memories_to_context"] = memory_cfg.get("add_to_context", True)

        if knowledge is not None:
            agent_kwargs["knowledge"] = knowledge

        # Merge tools: from config agent_kwargs + skill toolkits
        config_tools = agent_kwargs.pop("tools", []) or []
        all_tools = list(config_tools) + skill_toolkits

        super().__init__(
            model=model,
            db=db,
            name=self.agent_id,
            tools=all_tools if all_tools else None,
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
        self._tracer = get_tracer(self.agent_id, db=db)
        self._state = AgentState.IDLE

    def _resolve_model(self, cfg: dict) -> Model:
        provider = cfg.get("llm_provider") or get_config("llm_providers", "default")
        return get_llm_provider(provider)

    def _build_knowledge(self, knowledge_cfg: dict):
        """Build an Agno Knowledge object from config dict."""
        from pika.infra.db import get_knowledge

        collection = knowledge_cfg.get("collection", f"{self.agent_id}_knowledge")
        return get_knowledge(
            collection,
            embedder_name=knowledge_cfg.get("embedder"),
            max_results=knowledge_cfg.get("max_results", 10),
        )

    async def run(self, message: str, **kwargs) -> Any:
        self._state = AgentState.THINKING

        try:
            # Cache check
            if self._cache:
                async with self._tracer.span("cache.get", kind=SpanKind.TOOL_CALL, input=message) as s:
                    cached = await self._cache.get(self.agent_id, message)
                    s["output"] = "hit" if cached is not None else "miss"
                if cached is not None:
                    self._state = AgentState.DONE
                    return cached

            # Corrections
            if self._corrections:
                async with self._tracer.span("corrections.retrieve", kind=SpanKind.CORRECTION, input=message) as s:
                    corrections = await self._corrections.retrieve(message)
                    s["output"] = f"{len(corrections)} corrections"
                if corrections:
                    deps = kwargs.setdefault("dependencies", {})
                    deps["active_corrections"] = corrections
                    kwargs.setdefault("add_dependencies_to_context", True)

            # Main agent execution
            self._state = AgentState.EXECUTING
            async with self._tracer.span("agent.run", kind=SpanKind.AGENT_STEP, input=message) as s:
                result = await super().arun(message, **kwargs)
                s["output"] = result.content if hasattr(result, "content") else str(result)

            # Cache store
            if self._cache and result:
                await self._cache.set(self.agent_id, message, result)

            self._state = AgentState.DONE
            return result

        except Exception:
            self._state = AgentState.ERROR
            raise

    async def stream(self, message: str, **kwargs) -> AsyncIterator[str]:
        """Stream tokens from the agent response."""
        self._state = AgentState.EXECUTING
        try:
            async for chunk in await super().astream(message, **kwargs):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
            self._state = AgentState.DONE
        except Exception:
            self._state = AgentState.ERROR
            raise

    @property
    def state(self) -> AgentState:
        return self._state
