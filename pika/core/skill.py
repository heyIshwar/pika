"""BaseSkill — reusable capability bundle for pika agents."""
from __future__ import annotations

from typing import List


class BaseSkill:
    """
    Extend this to create a reusable skill that agents can declare.

    A Skill bundles one or more tool functions into a named capability.
    It compiles down to an Agno Toolkit so the agent framework can call it.

    Example:
        class WebSearchSkill(BaseSkill):
            skill_id = "web_search"
            description = "Can search the web and summarize results"

            def get_tools(self):
                from skills.web_search.tool import WebSearchTool
                t = WebSearchTool()
                return [t.search]
    """

    skill_id: str = ""
    description: str = ""

    def __init__(self):
        if not self.skill_id:
            raise ValueError("BaseSkill subclasses must set skill_id")

    def get_tools(self) -> List:
        """Return list of callable tool functions (decorated with @agno_tool)."""
        raise NotImplementedError(f"{self.__class__.__name__}.get_tools() not implemented")

    def as_toolkit(self):
        """Return an Agno-compatible Toolkit wrapping this skill's tools."""
        from agno.tools.toolkit import Toolkit

        tool_instructions = getattr(self, "tool_instructions", None)
        if tool_instructions is None and self.description:
            tool_instructions = [self.description]

        return Toolkit(
            name=self.skill_id,
            tools=self.get_tools(),
            instructions=tool_instructions,
            add_instructions=bool(tool_instructions),
        )
