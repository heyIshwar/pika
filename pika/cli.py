import asyncio
import sys

import typer
from rich.console import Console
from rich.prompt import Prompt

from pika.cli_commands.loader import load_agent

cli = typer.Typer(name="pika", help="pika agent framework CLI")
console = Console()


@cli.command("new")
def new(kind: str = typer.Argument(...), name: str = typer.Argument(...)):
    """Scaffold a new agent or tool."""
    from pika.cli_commands.scaffold import scaffold

    scaffold(kind, name)


def _run_interactive(agent_id: str, flavor: str = "pika") -> None:
    try:
        agent = load_agent(agent_id)
    except (ModuleNotFoundError, ValueError) as exc:
        console.print(f"[red]Agent not found: {agent_id}[/red] ({exc})")
        raise typer.Exit(code=1) from exc
    asyncio.run(_repl(agent, flavor=flavor))


@cli.command("run")
def run(agent_id: str = typer.Argument(...)):
    """Run an agent in interactive REPL mode."""
    _run_interactive(agent_id)


@cli.command("chu")
def chu(agent_id: str = typer.Argument(...)):
    """pika chu <agent_id> — run agent interactively (pikachu alias)."""
    _run_interactive(agent_id, flavor="chu")


@cli.command("choo")
def choo(agent_id: str = typer.Argument(...)):
    """pika choo <agent_id> — run agent interactively (pikachoo alias)."""
    _run_interactive(agent_id, flavor="choo")


@cli.command("serve")
def serve(
    port: int = typer.Option(8080, "--port", "-p"),
    host: str = typer.Option("0.0.0.0", "--host"),
):
    """Start the AgentOS FastAPI server."""
    from agno.os import AgentOS

    from pika.cli_commands.loader import load_all_agents
    from pika.infra.storage import get_storage

    agents = load_all_agents()
    db = get_storage()
    agent_os = AgentOS(agents=agents, db=db)
    app = agent_os.get_app()
    agent_os.serve(app=app, host=host, port=port)


@cli.command("check")
def check():
    """Validate registry.yaml."""
    from pika.cli_commands.registry import validate_registry

    validate_registry()


@cli.command("optimize")
def optimize(agent_id: str = typer.Argument(...)):
    """Run DSPy optimizer for an agent's prompt."""
    from pika.optimization.optimizer import run_optimizer

    asyncio.run(run_optimizer(agent_id))


@cli.command("eval")
def eval_cmd(agent_id: str = typer.Argument(...)):
    """Run LangFuse evaluations for an agent."""
    from pika.observability.eval import run_eval

    asyncio.run(run_eval(agent_id))


def execute():
    """pikachu <agent_id> — execute an agent interactively."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: pikachu <agent_id>[/red]")
        sys.exit(1)
    _run_interactive(sys.argv[1], flavor="chu")


def chu_main():
    """pika-chu <agent_id> — standalone entry for `pika chu`."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: pika-chu <agent_id>  (or: pika chu <agent_id>)[/red]")
        sys.exit(1)
    _run_interactive(sys.argv[1], flavor="chu")


def choo_main():
    """pika-choo <agent_id> — standalone entry for `pika choo`."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: pika-choo <agent_id>  (or: pika choo <agent_id>)[/red]")
        sys.exit(1)
    _run_interactive(sys.argv[1], flavor="choo")


_GREETINGS = {
    "pika": ("pika", "ready"),
    "chu": ("pika chu", "pika pika!"),
    "choo": ("pika choo", "choo choo!"),
}


async def _repl(agent, flavor: str = "pika"):
    label, tagline = _GREETINGS.get(flavor, _GREETINGS["pika"])
    console.print(f"[bold purple]{label}[/bold purple] > {agent.agent_id} {tagline}")
    while True:
        msg = Prompt.ask("[dim]you[/dim]")
        if msg.lower() in ("exit", "quit", "/q"):
            break
        result = await agent.run(msg)
        content = result.content if hasattr(result, "content") else str(result)
        console.print(f"[purple]agent[/purple]: {content}")


if __name__ == "__main__":
    cli()
