"""pika init — scaffold a new pika-powered project in the current directory."""
from __future__ import annotations

import pathlib

from rich.console import Console
from rich.prompt import Prompt

console = Console()

_PIKA_YAML = """\
pika:
  default_agent: orchestrator

  database:
    url: "{db_url}"

  vectordb:
    provider: lancedb
    path: .lance

  agno:
    enable_agentic_memory: false
    add_memories_to_context: false
    add_history_to_context: true
    num_history_runs: 5

  observability:
    langfuse_enabled: false
    otel_enabled: false

  optimization:
    dspy_lm: openai/gpt-4o-mini
"""

_REGISTRY_YAML = """\
agents: []
teams: []
skills: []
"""

_AGENT_STUB = '''\
"""Getting-started agent — replace with your own logic."""
from pika import BaseAgent


class GettingStartedAgent(BaseAgent):
    agent_id = "getting_started"
    description = "A friendly hello-world agent"
    instructions = [
        "Greet the user and answer their question concisely.",
    ]
'''


def scaffold_init():
    cwd = pathlib.Path(".")
    console.print("[bold purple]pika init[/bold purple] — scaffold a new pika project\n")

    db_url = Prompt.ask("Database URL", default="sqlite:///pika.db")

    pika_yaml = cwd / "pika.yaml"
    if pika_yaml.exists():
        overwrite = Prompt.ask("pika.yaml already exists. Overwrite?", choices=["y", "n"], default="n")
        if overwrite != "y":
            console.print("[yellow]Skipping pika.yaml[/yellow]")
        else:
            pika_yaml.write_text(_PIKA_YAML.format(db_url=db_url))
            console.print("  [green]✓[/green] pika.yaml")
    else:
        pika_yaml.write_text(_PIKA_YAML.format(db_url=db_url))
        console.print("  [green]✓[/green] pika.yaml")

    for d in ["agents/getting_started", "skills", "teams", "workflows", "scripts"]:
        (cwd / d).mkdir(parents=True, exist_ok=True)

    registry = cwd / "registry.yaml"
    if not registry.exists():
        registry.write_text(_REGISTRY_YAML)
        console.print("  [green]✓[/green] registry.yaml")

    agent_file = cwd / "agents/getting_started/agent.py"
    if not agent_file.exists():
        agent_file.write_text(_AGENT_STUB)
        console.print("  [green]✓[/green] agents/getting_started/agent.py")

    console.print("\n[bold]Done![/bold]  Run [cyan]pika serve[/cyan] to start the API server.")
    console.print("Or run [cyan]pika run[/cyan] to chat interactively.")
