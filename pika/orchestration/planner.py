"""
Planner: decomposes a task into steps and executes them over specialist agents.

Used by OrchestratorAgent in 'plan' mode.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class PlanStep:
    id: str
    agent_id: str
    task: str
    depends_on: List[str] = field(default_factory=list)
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TaskPlan:
    plan_id: str
    steps: List[PlanStep]

    @classmethod
    def from_dict(cls, data: dict) -> "TaskPlan":
        steps = [
            PlanStep(
                id=s.get("id", str(uuid4())),
                agent_id=s["agent_id"],
                task=s["task"],
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        return cls(plan_id=data.get("plan_id", str(uuid4())), steps=steps)


@dataclass
class PlanResult:
    plan_id: str
    outputs: Dict[str, str]  # step_id -> output
    errors: Dict[str, str]   # step_id -> error message
    merged_output: str = ""


class Planner:
    """
    Produce a TaskPlan from an LLM call and execute it over a dict of agents.
    """

    def __init__(self, model=None):
        self._model = model

    async def plan(self, task: str, available_agents: List[dict]) -> TaskPlan:
        """
        Ask the LLM to decompose `task` into steps assigned to available_agents.
        Returns a TaskPlan.
        """
        agent_descriptions = "\n".join(
            f"- {a['id']}: {a.get('description', '')}" for a in available_agents
        )
        prompt = (
            f"Decompose the following task into steps. Each step must be assigned to one "
            f"of the available agents.\n\n"
            f"Task: {task}\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            f"Return a JSON object with a 'steps' array. Each step has:\n"
            f"  id (string), agent_id (one of the agents above), task (string instruction), "
            f"depends_on (array of step ids this step waits for, can be empty).\n\n"
            f"Example:\n"
            f'{{"steps": [{{"id": "s1", "agent_id": "research_agent", "task": "Research X", "depends_on": []}}]}}'
        )

        if self._model is None:
            from pika.infra.db import get_llm_provider
            from pika.config.loader import get_config

            provider_cfg = get_config("llm_providers", "default")
            self._model = get_llm_provider(provider_cfg)

        from agno.agent import Agent

        planner_agent = Agent(model=self._model, markdown=False)
        response = await planner_agent.arun(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        plan_data = self._parse_json(content)
        plan_data["plan_id"] = str(uuid4())
        return TaskPlan.from_dict(plan_data)

    async def execute(self, plan: TaskPlan, agents: Dict[str, Any]) -> PlanResult:
        """
        Execute plan steps topologically.
        Independent steps run in parallel via asyncio.gather.
        """
        from pika.bus.factory import get_bus

        bus = get_bus()
        completed: Dict[str, str] = {}
        errors: Dict[str, str] = {}

        remaining = list(plan.steps)

        while remaining:
            ready = [
                s for s in remaining
                if all(dep in completed for dep in s.depends_on)
            ]
            if not ready:
                # Circular dependency or missing deps
                for s in remaining:
                    errors[s.id] = "Dependency not met — possible cycle"
                break

            results = await asyncio.gather(
                *[self._run_step(s, agents, completed, plan.plan_id) for s in ready],
                return_exceptions=True,
            )
            for step, result in zip(ready, results):
                remaining.remove(step)
                if isinstance(result, Exception):
                    errors[step.id] = str(result)
                else:
                    completed[step.id] = result
                    await bus.publish(f"plan.{plan.plan_id}.{step.id}", result)

        merged = "\n\n".join(
            f"[{plan.steps[i].task}]\n{v}"
            for i, (k, v) in enumerate(completed.items())
        )
        return PlanResult(
            plan_id=plan.plan_id,
            outputs=completed,
            errors=errors,
            merged_output=merged,
        )

    async def _run_step(
        self,
        step: PlanStep,
        agents: Dict[str, Any],
        context: Dict[str, str],
        plan_id: str,
    ) -> str:
        agent = agents.get(step.agent_id)
        if agent is None:
            raise ValueError(f"Agent '{step.agent_id}' not found for plan step '{step.id}'")

        task_with_context = step.task
        if step.depends_on and context:
            prior = "\n".join(
                f"Step {dep}: {context[dep]}" for dep in step.depends_on if dep in context
            )
            task_with_context = f"Prior results:\n{prior}\n\nYour task: {step.task}"

        result = await agent.run(task_with_context)
        return result.content if hasattr(result, "content") else str(result)

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"steps": []}
