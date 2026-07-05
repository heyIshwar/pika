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


def create_app(include_agent_routes: bool = True) -> FastAPI:
    _maybe_install_compat()
    try:
        from pika.observability.langfuse_otel import install_langfuse_otel

        install_langfuse_otel()
    except Exception:
        pass

    app = FastAPI(
        title="Pika Agent Framework",
        description="REST API for pika agents and teams",
        version=pika.__version__,
    )

    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)

    app.include_router(health.router)
    app.include_router(traces.router)
    if include_agent_routes:
        app.include_router(agents.router)
        app.include_router(teams.router)

    return app


def _maybe_install_compat() -> None:
    try:
        from pika.config.loader import get_settings

        if get_settings().get("compat", {}).get("gemini_tool_names"):
            from pika.compat.gemini import install as install_gemini_compat

            install_gemini_compat()
    except Exception:
        pass


def create_os():
    """Build an Agno AgentOS on top of the pika FastAPI app.

    Mounts AgentOS's full REST/WebSocket surface (agent/team run+stream,
    knowledge, memory, sessions, evals, MCP) onto pika's own app, so pika's
    TenantMiddleware/AuthMiddleware and custom routes (health, traces) stay
    intact.

    pika's own `/agents` and `/teams` routes are deliberately left out here:
    they'd sit at the exact same paths as AgentOS's own agent/team routers,
    and this Agno version's route-conflict detection doesn't reliably catch
    that (it can't see routes wrapped in FastAPI's newer `_IncludedRouter`
    grouping) — so pika's simpler routes would silently shadow AgentOS's.
    Use `pika serve --no-os` if you want pika's standalone agents/teams API
    instead of AgentOS.
    """
    from agno.os import AgentOS

    from pika.cli.commands.loader import load_all_agents, load_all_teams
    from pika.infra.storage import get_storage
    from pika.observability.langfuse_otel import install_langfuse_otel

    # Must happen before load_all_agents()/load_all_teams(): agent __init__
    # builds a Langfuse client immediately, which reads credentials from
    # os.environ at construction time.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    _maybe_install_compat()
    install_langfuse_otel()

    pika_agents = load_all_agents()
    pika_teams = load_all_teams()

    knowledge_bases = []
    seen_ids = set()
    for runner in [*pika_agents, *pika_teams]:
        kb = getattr(runner, "knowledge", None)
        if kb is not None and id(kb) not in seen_ids:
            seen_ids.add(id(kb))
            knowledge_bases.append(kb)

    agent_os = AgentOS(
        id="pika",
        name="Pika Agent Framework",
        description="Agno AgentOS for pika-registered agents and teams",
        db=get_storage(),
        agents=pika_agents or None,
        teams=pika_teams or None,
        knowledge=knowledge_bases or None,
        base_app=create_app(include_agent_routes=False),
    )
    return agent_os.get_app()
