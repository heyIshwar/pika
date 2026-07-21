"""Load agentskills.io / Hermes SKILL.md files into Pika BaseSkill."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from pika.core.skill import BaseSkill

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def parse_skill_md(path: Path | str) -> Tuple[Dict[str, Any], str]:
    """Parse SKILL.md → (frontmatter dict, markdown body)."""
    text = Path(path).expanduser().read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text.strip()
    front_raw, body = match.group(1), match.group(2)
    front = yaml.safe_load(front_raw) or {}
    if not isinstance(front, dict):
        front = {}
    return front, body.strip()


class HermesSkillAdapter(BaseSkill):
    """BaseSkill whose description / tool_instructions come from SKILL.md.

    Subclasses still implement ``get_tools()``. Point ``skill_md_path`` at an
    agentskills.io / Hermes skill directory or a SKILL.md file.
    """

    skill_md_path: str = ""

    def __init__(self, skill_md_path: Optional[str] = None):
        path = skill_md_path or self.skill_md_path
        if not path:
            raise ValueError(f"{self.__class__.__name__} requires skill_md_path")

        md_path = Path(path).expanduser()
        if md_path.is_dir():
            md_path = md_path / "SKILL.md"
        if not md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found: {md_path}")

        front, body = parse_skill_md(md_path)
        name = str(front.get("name") or md_path.parent.name).replace("-", "_")
        self.skill_id = name
        self.description = str(front.get("description") or name)
        self.tool_instructions: List[str] = [body] if body else [self.description]
        self._frontmatter = front
        self._skill_md_path = md_path
        self._skill_dir = md_path.parent
        super().__init__()

    @property
    def skill_dir(self) -> Path:
        return self._skill_dir

    @property
    def frontmatter(self) -> Dict[str, Any]:
        return self._frontmatter
