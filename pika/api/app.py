"""Pika FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI

# Load .env on startup
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pika
from pika.api.middleware import AuthMiddleware, TenantMiddleware
from pika.api.routes import agents, health, teams, traces


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pika Agent Framework",
        description="REST API for pika agents and teams",
        version=pika.__version__,
    )

    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(teams.router)
    app.include_router(traces.router)

    return app


def create_os():
    """Build an Agno AgentOS on top of the pika FastAPI app.

    Mounts AgentOS's full REST/WebSocket surface (agent/team run+stream,
    knowledge, memory, sessions, evals, MCP) onto pika's own `create_app()`,
    so pika's TenantMiddleware/AuthMiddleware and custom routes stay intact.
    """
    from agno.os import AgentOS

    from pika.cli.commands.loader import load_all_agents, load_all_teams
    from pika.infra.storage import get_storage

    agents = load_all_agents()
    teams = load_all_teams()

    knowledge_bases = []
    seen_ids = set()
    for runner in [*agents, *teams]:
        kb = getattr(runner, "knowledge", None)
        if kb is not None and id(kb) not in seen_ids:
            seen_ids.add(id(kb))
            knowledge_bases.append(kb)

    agent_os = AgentOS(
        id="pika",
        name="Pika Agent Framework",
        description="Agno AgentOS for pika-registered agents and teams",
        db=get_storage(),
        agents=agents or None,
        teams=teams or None,
        knowledge=knowledge_bases or None,
        base_app=create_app(),
    )
    return agent_os.get_app()
