from __future__ import annotations

from typing import Any, Optional

from agno.models.base import Model
from agno.team import Team

from pika.config.loader import get_config
from pika.infra.db import get_llm_provider
from pika.infra.storage import get_storage


class BaseTeam(Team):
    """
    Extend this to create a multi-agent team.

    Example:
        class ResearchTeam(BaseTeam):
            team_id = 'research_team'
            members = [ResearchAgent(), WriterAgent()]
            mode = 'coordinate'
    """

    team_id: str = ""

    def __init__(self, **kwargs):
        if not self.team_id:
            raise ValueError("BaseTeam subclasses must set team_id")

        cfg = get_config("teams", self.team_id)
        db = get_storage()
        model: Optional[Model] = kwargs.pop("model", None) or self._resolve_model(cfg)
        members = kwargs.pop("members", None)
        team_kwargs = cfg.get("team_kwargs", {})
        super().__init__(model=model, db=db, members=members, **team_kwargs, **kwargs)
        self.orch_mode: str = cfg.get("orch_mode", "route")

    def _resolve_model(self, cfg: dict) -> Model:
        provider = cfg.get("llm_provider") or get_config("llm_providers", "default")
        return get_llm_provider(provider)

    @property
    def agent_id(self) -> str:
        return self.team_id

    async def run(self, message: str, **kwargs) -> Any:
        return await self.arun(message, **kwargs)
