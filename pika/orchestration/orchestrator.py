"""Default orchestrator — routes, plans, or parallelises tasks across registered agents."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from pika.cli.commands.loader import list_agent_ids, load_agent
from pika.core.team import BaseTeam


class OrchestratorAgent(BaseTeam):
    """
    Multi-mode orchestrator over all registry agents.

    Modes (set via config/teams/orchestrator.yaml → orch_mode):
      route     — LLM picks one agent and delegates (default, current behaviour)
      plan      — LLM decomposes task into steps; Planner executes them
      parallel  — LLM identifies independent sub-tasks; runs all agents in parallel
    """

    team_id = "orchestrator"

    def __init__(self, **kwargs):
        members = []
        for agent_id in list_agent_ids():
            if agent_id == self.team_id:
                continue
            members.append(load_agent(agent_id))

        if not members:
            raise ValueError(
                "Orchestrator needs at least one other agent in registry.yaml"
            )

        super().__init__(members=members, **kwargs)

        self._agent_map: Dict[str, Any] = {m.agent_id: m for m in members}

    async def run(self, message: str, **kwargs) -> Any:  # type: ignore[override]
        if self.orch_mode == "plan":
            return await self._run_plan(message, **kwargs)
        if self.orch_mode == "parallel":
            return await self._run_parallel(message, **kwargs)
        return await super().run(message, **kwargs)

    # ------------------------------------------------------------------
    # Plan mode
    # ------------------------------------------------------------------

    async def _run_plan(self, message: str, **kwargs) -> Any:
        from pika.orchestration.planner import Planner

        planner = Planner()
        agent_manifests = [
            {"id": aid, "description": getattr(a, "description", "")}
            for aid, a in self._agent_map.items()
        ]
        plan = await planner.plan(message, agent_manifests)
        result = await planner.execute(plan, self._agent_map)

        class _Result:
            content = result.merged_output

        return _Result()

    # ------------------------------------------------------------------
    # Parallel mode
    # ------------------------------------------------------------------

    async def _run_parallel(self, message: str, **kwargs) -> Any:
        results = await asyncio.gather(
            *[agent.run(message, **kwargs) for agent in self._agent_map.values()],
            return_exceptions=True,
        )
        parts: List[str] = []
        for agent_id, res in zip(self._agent_map.keys(), results):
            if isinstance(res, Exception):
                parts.append(f"[{agent_id}] Error: {res}")
            else:
                content = res.content if hasattr(res, "content") else str(res)
                parts.append(f"[{agent_id}]\n{content}")

        merged = "\n\n---\n\n".join(parts)

        class _Result:
            content = merged

        return _Result()
