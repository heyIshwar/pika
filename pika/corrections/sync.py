"""Keep SQL agent_corrections and vector index in sync."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pika.corrections.models import AgentCorrection
from pika.corrections.store import CorrectionStore
from pika.infra.db import get_engine


async def sync_agent_corrections(agent_id: str):
    store = CorrectionStore(agent_id=agent_id)

    with Session(get_engine()) as session:
        active = session.scalars(
            select(AgentCorrection).where(
                AgentCorrection.agent_id == agent_id,
                AgentCorrection.active.is_(True),
            )
        ).all()

    if store._vdb is None:
        return

    try:
        store._vdb.delete()
    except Exception:
        pass

    if not active:
        return

    from agno.knowledge.document.base import Document

    docs = [
        Document(
            id=str(row.id),
            content=f"{row.intent}: {row.correction}",
            meta_data={"agent_id": agent_id},
        )
        for row in active
    ]
    store._vdb.insert(content_hash=agent_id, documents=docs)
