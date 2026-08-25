"""pika knowledge — ingest existing docs/infra and databases into an agent's RAG knowledge base."""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()

knowledge_app = typer.Typer(help="Ingest content into an agent's knowledge base (RAG)")


@knowledge_app.command("add")
def add(
    agent_id: str = typer.Argument(..., help="Agent id whose knowledge base to update"),
    path: str = typer.Option(..., "--path", "-p", help="File, directory, or URL to ingest"),
    fmt: str = typer.Option("auto", "--format", "-f", help="Ingest format: auto, okf"),
):
    """Ingest a file, directory, or URL into an agent's knowledge base."""
    import asyncio
    import pathlib

    from pika.knowledge import ingest_path

    console.print(f"[bold purple]pika knowledge add[/bold purple] {agent_id} <- {path}")
    if fmt == "okf":
        from pika.knowledge.ingest import _knowledge_for
        from pika.knowledge.okf import ingest_okf_bundle

        async def _okf():
            kb = _knowledge_for(agent_id)
            return await ingest_okf_bundle(kb, [pathlib.Path(path)])

        report = asyncio.run(_okf())
        console.print(f"  [green]✓[/green] ingested {report.ok_count} OKF concept(s)")
        if report.skipped:
            console.print(f"  [dim]skipped {len(report.skipped)} non-OKF/reserved file(s)[/dim]")
        _print_failures(report)
        if report.failed:
            raise typer.Exit(code=1)
        return

    report = asyncio.run(ingest_path(agent_id, path))
    console.print(f"  [green]✓[/green] ingested {report.ok_count} item(s)")
    _print_failures(report)
    if report.failed:
        raise typer.Exit(code=1)


def _print_failures(report) -> None:
    """Print per-item ingest failures so partial runs are visible."""
    for failure in report.failed:
        console.print(
            f"  [red]✗[/red] {failure['target']}: {failure['error']}"
        )


@knowledge_app.command("add-db")
def add_db(
    agent_id: str = typer.Argument(..., help="Agent id whose knowledge base to update"),
    db_url: Optional[str] = typer.Option(
        None, "--db-url", help="Existing database URL to introspect (defaults to pika's own DATABASE_URL)"
    ),
):
    """Introspect an existing SQL database's schema and ingest it as searchable knowledge."""
    import asyncio

    from pika.knowledge import ingest_database_schema

    console.print(f"[bold purple]pika knowledge add-db[/bold purple] {agent_id} <- {db_url or 'DATABASE_URL'}")
    count = asyncio.run(ingest_database_schema(agent_id, db_url=db_url))
    console.print(f"  [green]✓[/green] ingested schema for {count} table(s)")


@knowledge_app.command("list")
def list_content(agent_id: str = typer.Argument(..., help="Agent id whose knowledge base to inspect")):
    """List content ingested into an agent's knowledge base."""
    import asyncio

    from pika.knowledge.ingest import _knowledge_for

    async def _list():
        knowledge = _knowledge_for(agent_id)
        return await knowledge.aget_content()

    contents, total = asyncio.run(_list())

    if not contents:
        console.print("[dim]No content ingested yet.[/dim]")
        return

    table = Table(title=f"Knowledge for {agent_id} (total={total})")
    table.add_column("name")
    table.add_column("source")
    table.add_column("status")

    for c in contents:
        source = c.path or c.url or (c.metadata or {}).get("table") or "-"
        table.add_row(str(c.name or c.id), str(source), str(c.status.value if c.status else ""))

    console.print(table)
