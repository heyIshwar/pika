"""Detect whether user message matches correction intents."""

from __future__ import annotations

import json
import re

from pika.config.loader import get_config
from pika.infra.db import get_llm_provider


class CorrectionDetector:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._llm = get_llm_provider(get_config("llm_providers", "default"))

    async def classify(self, message: str, candidates: list[str]) -> list[str]:
        if not candidates:
            return []

        prompt = (
            "Given this user message:\n"
            f'"{message}"\n\n'
            "Which of these correction intents apply? Return only applicable ones as JSON list.\n\n"
            + "\n".join(f"- {c}" for c in candidates)
        )
        result = await self._llm.aresponse(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        match = re.search(r"\[.*?\]", content or "", re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
