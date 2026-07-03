import asyncio
import sys
from typing import Optional

# Load .env automatically when CLI is used
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import typer
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt
from rich.table import Table

from pika.cli.commands.loader import load_agent, resolve_agent_id
from pika.cli.commands.knowledge import knowledge_app
from pika.cli.aliases import interactive_command_names

cli = typer.Typer(name="pika", help="pika agent framework CLI")
console = Console()

trace_app = typer.Typer(help="Trace inspection commands")
cli.add_typer(trace_app, name="trace")
cli.add_typer(knowledge_app, name="knowledge")


def _register_interactive_commands(canonical: str, flavor: str, doc: str) -> None:
    def make_handler(name: str, flav: str):
        is_alias = name != canonical

        def handler(
            agent_id: Optional[str] = typer.Argument(None, help="Agent id (default: orchestrator)"),
            stream: bool = typer.Option(False, "--stream", "-s", help="Stream output token-by-token"),
        ) -> None:
            _run_interactive(agent_id, flavor=flav, stream=stream)

        handler.__name__ = name.replace("-", "_")
        handler.__doc__ = f"Alias for `pika {canonical}`." if is_alias else doc
        return handler

    for name in interactive_command_names(canonical):
        cli.command(name)(make_handler(name, flavor))


@cli.command("new")
def new(kind: str = typer.Argument(...), name: str = typer.Argument(...)):
    """Scaffold a new agent or tool."""
    from pika.cli.commands.scaffold import scaffold

    scaffold(kind, name)


@cli.command("init")
def init():
    """Scaffold a new pika-powered project in the current directory."""
    from pika.cli.commands.init import scaffold_init

    scaffold_init()


@cli.command("connect")
def connect(
    api_base_url: str = typer.Argument(..., help="Base URL of the external API"),
    name: str = typer.Option(..., "--name", "-n", help="Tool name/identifier"),
):
    """Generate BaseTool stubs from an external OpenAPI spec."""
    from pika.cli.commands.connect import connect_api

    connect_api(api_base_url, name)


def _run_interactive(
    agent_id: Optional[str] = None,
    flavor: str = "pika",
    stream: bool = False,
) -> None:
    resolved = resolve_agent_id(agent_id)
    try:
        runner = load_agent(resolved)
    except (ModuleNotFoundError, ValueError) as exc:
        console.print(f"[red]Agent not found: {resolved}[/red] ({exc})")
        raise typer.Exit(code=1) from exc
    asyncio.run(_repl(runner, flavor=flavor, stream=stream))


@cli.command("run")
def run(
    agent_id: Optional[str] = typer.Argument(None, help="Agent id (default: orchestrator)"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream output token-by-token"),
):
    """Run an agent in interactive REPL mode."""
    _run_interactive(agent_id, stream=stream)


_register_interactive_commands("chu", "chu", "pika chu [agent_id] — run agent interactively.")
_register_interactive_commands("choo", "choo", "pika choo [agent_id] — run agent interactively.")


@cli.command("serve")
def serve(
    port: int = typer.Option(8080, "--port", "-p"),
    host: str = typer.Option("0.0.0.0", "--host"),
    no_os: bool = typer.Option(False, "--no-os", help="Skip Agno AgentOS, serve only pika's own routes"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev only)"),
):
    """Start the pika FastAPI server (mounts Agno AgentOS by default)."""
    import pathlib

    import uvicorn

    app_factory = "pika.api.app:create_app" if no_os else "pika.api.app:create_os"
    uvicorn.run(
        app_factory,
        factory=True,
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(pathlib.Path.cwd())] if reload else None,
    )


@cli.command("check")
def check():
    """Validate registry.yaml."""
    from pika.cli.commands.registry import validate_registry

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


# ------------------------------------------------------------------
# Trace subcommands
# ------------------------------------------------------------------


@trace_app.command("list")
def trace_list(
    agent_id: Optional[str] = typer.Option(None, "--agent-id", "-a"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """List recent traces stored in the pika DB."""
    from pika.infra.storage import get_storage

    db = get_storage()
    try:
        traces, total = db.get_traces(agent_id=agent_id, limit=limit)
    except Exception as exc:
        console.print(f"[red]Error reading traces: {exc}[/red]")
        raise typer.Exit(1)

    if not traces:
        console.print("[dim]No traces found.[/dim]")
        return

    table = Table(title=f"Traces (total={total})")
    table.add_column("trace_id", max_width=36)
    table.add_column("name")
    table.add_column("status")
    table.add_column("agent_id")
    table.add_column("duration_ms")
    table.add_column("spans")
    table.add_column("created_at", max_width=25)

    for t in traces:
        d = t.__dict__ if hasattr(t, "__dict__") else (t._asdict() if hasattr(t, "_asdict") else t)
        table.add_row(
            str(d.get("trace_id", ""))[:36],
            str(d.get("name", "")),
            str(d.get("status", "")),
            str(d.get("agent_id", "") or ""),
            str(d.get("duration_ms", "")),
            str(d.get("total_spans", "")),
            str(d.get("created_at", ""))[:25],
        )

    console.print(table)


@trace_app.command("show")
def trace_show(trace_id: str = typer.Argument(..., help="Trace ID to inspect")):
    """Show spans for a specific trace."""
    from pika.infra.storage import get_storage

    db = get_storage()
    try:
        spans = db.get_spans(trace_id=trace_id)
    except Exception as exc:
        console.print(f"[red]Error reading spans: {exc}[/red]")
        raise typer.Exit(1)

    if not spans:
        console.print(f"[dim]No spans found for trace {trace_id}.[/dim]")
        return

    table = Table(title=f"Spans for trace {trace_id}")
    table.add_column("span_id", max_width=16)
    table.add_column("name")
    table.add_column("kind")
    table.add_column("status")
    table.add_column("duration_ms")

    for span in spans:
        d = span.__dict__ if hasattr(span, "__dict__") else (span._asdict() if hasattr(span, "_asdict") else span)
        table.add_row(
            str(d.get("span_id", ""))[:16],
            str(d.get("name", "")),
            str(d.get("span_kind", "")),
            str(d.get("status_code", "")),
            str(d.get("duration_ms", "")),
        )

    console.print(table)


# ------------------------------------------------------------------
# REPL
# ------------------------------------------------------------------


def chu_main():
    """pikachu / pika-chu [agent_id] — standalone entry for `pika chu`."""
    agent_id = sys.argv[1] if len(sys.argv) > 1 else None
    _run_interactive(agent_id, flavor="chu")


def choo_main():
    """pika-choo / pikachoo [agent_id] — standalone entry for `pika choo`."""
    agent_id = sys.argv[1] if len(sys.argv) > 1 else None
    _run_interactive(agent_id, flavor="choo")


def execute() -> None:
    """Backward-compatible alias for chu_main / pikachu entrypoint."""
    chu_main()


_GREETINGS = {
    "pika": ("pika", "ready"),
    "chu": ("pika chu", "pika pika!"),
    "choo": ("pika choo", "choo choo!"),
}


async def _repl(runner, flavor: str = "pika", stream: bool = False):
    label, tagline = _GREETINGS.get(flavor, _GREETINGS["pika"])
    console.print(f"[bold purple]{label}[/bold purple] > {runner.agent_id} {tagline}")
    while True:
        msg = Prompt.ask("[dim]you[/dim]")
        if msg.lower() in ("exit", "quit", "/q"):
            break

        if stream and hasattr(runner, "stream"):
            with Live("", console=console, refresh_per_second=20) as live:
                buf = ""
                async for chunk in runner.stream(msg):
                    buf += chunk
                    live.update(f"[purple]agent[/purple]: {buf}")
        else:
            result = await runner.run(msg)
            content = result.content if hasattr(result, "content") else str(result)
            console.print(f"[purple]agent[/purple]: {content}")


if __name__ == "__main__":
    cli()
