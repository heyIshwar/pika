from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional
from uuid import uuid4

from agno.agent import Agent
from agno.models.base import Model

from pika.config.loader import get_config, get_settings
from pika.core.agno_context import (
    apply_knowledge_defaults,
    collect_context_kwargs,
    load_training_examples,
)
from pika.corrections.store import CorrectionStore
from pika.infra.cache import CacheManager, CachedResponse
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
        apply_knowledge_defaults(agent_kwargs, has_knowledge=knowledge is not None)

        # Merge tools: from config agent_kwargs + skill toolkits
        config_tools = agent_kwargs.pop("tools", []) or []
        all_tools = list(config_tools) + skill_toolkits

        description = (
            kwargs.pop("description", None)
            or agent_kwargs.pop("description", None)
            or getattr(self, "description", None)
        )
        instructions = (
            kwargs.pop("instructions", None)
            or agent_kwargs.pop("instructions", None)
            or getattr(self, "instructions", None)
        )

        context_kwargs = collect_context_kwargs(self, agent_kwargs, kwargs)
        if context_kwargs.get("additional_input") is None:
            few_shot = load_training_examples(self.agent_id)
            if few_shot:
                context_kwargs["additional_input"] = few_shot

        super().__init__(
            model=model,
            db=db,
            id=self.agent_id,
            name=self.agent_id,
            description=description,
            instructions=instructions,
            tools=all_tools if all_tools else None,
            **context_kwargs,
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

    def _trace_input(self, input: Any) -> str:
        if isinstance(input, str):
            return input
        return str(input)

    async def _apply_corrections(self, message: str, kwargs: dict) -> None:
        if not self._corrections:
            return
        async with self._tracer.span(
            "corrections.retrieve", kind=SpanKind.CORRECTION, input=message
        ) as s:
            corrections = await self._corrections.retrieve(message)
            s["output"] = f"{len(corrections)} corrections"
        if corrections:
            deps = kwargs.setdefault("dependencies", {})
            deps["active_corrections"] = corrections
            kwargs.setdefault("add_dependencies_to_context", True)

    def _prepare_trace_kwargs(self, kwargs: dict) -> dict:
        run_id = kwargs.get("run_id") or str(uuid4())
        kwargs["run_id"] = run_id
        return {
            "session_id": kwargs.get("session_id"),
            "user_id": kwargs.get("user_id"),
            "run_id": run_id,
        }

    async def _traced_arun(self, message: str, **kwargs) -> Any:
        self._state = AgentState.THINKING
        trace_input = self._trace_input(message)
        trace_ctx = self._prepare_trace_kwargs(kwargs)

        try:
            async with self._tracer.run_context(**trace_ctx) as trace_id:
                async with self._tracer.span(
                    "run",
                    kind=SpanKind.AGENT_STEP,
                    input=trace_input,
                    observation_name=trace_id,
                ) as run:
                    # Cache check
                    if self._cache:
                        async with self._tracer.span(
                            "cache.get", kind=SpanKind.TOOL_CALL, input=trace_input
                        ) as s:
                            cached = await self._cache.get(self.agent_id, trace_input)
                            s["output"] = "hit" if cached is not None else "miss"
                        if cached is not None:
                            self._state = AgentState.DONE
                            run["output"] = cached.content if hasattr(cached, "content") else str(cached)
                            return cached

                    await self._apply_corrections(trace_input, kwargs)

                    # Main agent execution
                    self._state = AgentState.EXECUTING
                    async with self._tracer.span(
                        "agent.run", kind=SpanKind.AGENT_STEP, input=trace_input
                    ) as s:
                        result = await super().arun(message, stream=False, **kwargs)
                        s["output"] = result.content if hasattr(result, "content") else str(result)

                    # Cache store
                    if self._cache and result:
                        await self._cache.set(self.agent_id, trace_input, result)

                    self._state = AgentState.DONE
                    run["output"] = result.content if hasattr(result, "content") else str(result)
                    return result

        except Exception:
            self._state = AgentState.ERROR
            raise

    async def _traced_arun_stream(self, input, **kwargs):
        """AgentOS chat uses stream=True — trace cache/corrections/run here too."""
        self._state = AgentState.THINKING
        trace_input = self._trace_input(input)
        trace_ctx = self._prepare_trace_kwargs(kwargs)

        try:
            async with self._tracer.run_context(**trace_ctx) as trace_id:
                async with self._tracer.span(
                    "run",
                    kind=SpanKind.AGENT_STEP,
                    input=trace_input,
                    observation_name=trace_id,
                ) as run:
                    if self._cache:
                        async with self._tracer.span(
                            "cache.get", kind=SpanKind.TOOL_CALL, input=trace_input
                        ) as s:
                            cached = await self._cache.get(self.agent_id, trace_input)
                            s["output"] = "hit" if cached is not None else "miss"
                        if cached is not None:
                            self._state = AgentState.DONE
                            run["output"] = cached.content if hasattr(cached, "content") else str(cached)
                            async with self._tracer.span(
                                "agent.run", kind=SpanKind.AGENT_STEP, input=trace_input
                            ) as s:
                                s["output"] = run["output"]
                                yield cached
                            return

                    await self._apply_corrections(trace_input, kwargs)

                    self._state = AgentState.EXECUTING
                    stream_gen = super().arun(input, stream=True, **kwargs)
                    async with self._tracer.span(
                        "agent.run", kind=SpanKind.AGENT_STEP, input=trace_input
                    ) as s:
                        output_parts: list[str] = []
                        async for chunk in stream_gen:
                            content = getattr(chunk, "content", None)
                            if content:
                                output_parts.append(str(content))
                            yield chunk
                        if output_parts:
                            full_output = "".join(output_parts)
                            # Same truncation policy as Tracer.span() — consistent
                            # across DB spans and Langfuse (SDK or OTEL export).
                            from pika.observability.tracing import truncate_trace_content

                            truncated = truncate_trace_content(full_output)
                            s["output"] = truncated
                            run["output"] = truncated
                            if self._cache:
                                # The streaming path used to read the cache but never
                                # fill it — streamed answers were cache-invisible.
                                await self._cache.set(
                                    self.agent_id,
                                    trace_input,
                                    CachedResponse(content=full_output),
                                )

                    self._state = AgentState.DONE

        except Exception:
            self._state = AgentState.ERROR
            raise

    def arun(self, input, *, stream=None, **kwargs):  # type: ignore[override]
        """Wrap Agno's arun so AgentOS / serve path gets Langfuse spans too."""
        if stream:
            return self._traced_arun_stream(input, **kwargs)
        return self._traced_arun(input, **kwargs)

    async def run(self, message: str, **kwargs) -> Any:
        return await self._traced_arun(message, **kwargs)

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
