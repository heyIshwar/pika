import importlib
import pathlib
import sys

import yaml

from pika.agent import BaseAgent


def _project_root() -> pathlib.Path:
    return pathlib.Path.cwd()


def _ensure_project_on_path():
    root = str(_project_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_agent(agent_id: str) -> BaseAgent:
    _ensure_project_on_path()
    mod = importlib.import_module(f"agents.{agent_id}.agent")
    classes = [
        v
        for v in vars(mod).values()
        if isinstance(v, type) and issubclass(v, BaseAgent) and v is not BaseAgent
    ]
    if not classes:
        raise ValueError(f"No BaseAgent subclass found in agents/{agent_id}/agent.py")
    return classes[0]()


def load_all_agents() -> list[BaseAgent]:
    _ensure_project_on_path()
    registry_path = _project_root() / "registry.yaml"
    if not registry_path.exists():
        return []

    data = yaml.safe_load(registry_path.read_text()) or {}
    agents = []
    for item in data.get("agents", []):
        try:
            agents.append(load_agent(item["id"]))
        except Exception as exc:
            print(f"Warning: could not load agent {item['id']}: {exc}")
    return agents
