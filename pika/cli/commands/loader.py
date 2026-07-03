import importlib
import pathlib
import sys

import yaml

from pika.core.agent import BaseAgent
from pika.config.loader import get_settings
from pika.core.team import BaseTeam

Runner = BaseAgent | BaseTeam


def _project_root() -> pathlib.Path:
    return pathlib.Path.cwd()


def _ensure_project_on_path():
    root = str(_project_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_registry() -> dict:
    _ensure_project_on_path()
    registry_path = _project_root() / "registry.yaml"
    if not registry_path.exists():
        return {}
    return yaml.safe_load(registry_path.read_text()) or {}


def list_agent_ids() -> list[str]:
    """Return agent IDs from registry (excludes teams)."""
    data = load_registry()
    return [item["id"] for item in data.get("agents", [])]


def list_team_ids() -> list[str]:
    """Return team IDs from registry."""
    data = load_registry()
    return [item["id"] for item in data.get("teams", [])]


def list_runnable_ids() -> list[str]:
    """Return all loadable agent and team IDs."""
    return list_agent_ids() + list_team_ids()


def get_default_agent_id() -> str:
    return get_settings().get("default_agent", "orchestrator")


def resolve_agent_id(agent_id: str | None) -> str:
    return agent_id if agent_id else get_default_agent_id()


def _load_from_module(mod, source: str) -> Runner:
    classes = [
        v
        for v in vars(mod).values()
        if isinstance(v, type)
        and (
            (issubclass(v, BaseAgent) and v is not BaseAgent)
            or (issubclass(v, BaseTeam) and v is not BaseTeam)
        )
    ]
    if not classes:
        raise ValueError(f"No BaseAgent/BaseTeam subclass in {source}")
    return classes[0]()


def load_agent(agent_id: str) -> Runner:
    _ensure_project_on_path()
    errors: list[str] = []

    for prefix in ("agents", "teams"):
        module_path = f"{prefix}.{agent_id}.agent"
        try:
            mod = importlib.import_module(module_path)
            return _load_from_module(mod, f"{prefix}/{agent_id}/agent.py")
        except ModuleNotFoundError as exc:
            if exc.name and not exc.name.startswith(("agents.", "teams.")):
                raise ModuleNotFoundError(
                    f"Missing dependency while loading '{agent_id}': {exc.name}. "
                    f"Try: pip install {exc.name}"
                ) from exc
            errors.append(str(exc))
            continue
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load '{agent_id}' from {prefix}/{agent_id}/agent.py: {exc}"
            ) from exc

    raise ModuleNotFoundError(
        f"No module for '{agent_id}' in agents/ or teams/. "
        + "; ".join(errors)
    )


def load_all_agents() -> list[BaseAgent]:
    _ensure_project_on_path()
    data = load_registry()
    agents = []
    for item in data.get("agents", []):
        try:
            runner = load_agent(item["id"])
            if isinstance(runner, BaseAgent):
                agents.append(runner)
        except Exception as exc:
            print(f"Warning: could not load agent {item['id']}: {exc}")
    return agents


def load_all_teams() -> list[BaseTeam]:
    _ensure_project_on_path()
    data = load_registry()
    teams = []
    for item in data.get("teams", []):
        try:
            runner = load_agent(item["id"])
            if isinstance(runner, BaseTeam):
                teams.append(runner)
        except Exception as exc:
            print(f"Warning: could not load team {item['id']}: {exc}")
    return teams
