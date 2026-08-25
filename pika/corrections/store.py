from __future__ import annotations

import os
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from pika.config.loader import get_config
from pika.corrections.models import AgentCorrection, init_corrections_db
from pika.infra.db import get_engine


class CorrectionStore:
    """SQL-backed correction store with optional LanceDB semantic search."""

    def __init__(self, agent_id: str, tenant_id: str | None = None):
        init_corrections_db()
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        cfg = get_config("agents", agent_id).get("corrections", {})
        self._top_k = cfg.get("top_k", 5)
        self._score_threshold = cfg.get("score_threshold", 0.75)
        self._vdb = self._init_vector_db()

    def _init_vector_db(self):
        if os.getenv("OPENAI_API_KEY"):
            try:
                from agno.knowledge.embedder.openai import OpenAIEmbedder
                from agno.vectordb.lancedb import LanceDb

                path = ".lance"
                return LanceDb(
                    uri=path,
                    table_name=f"corrections_{self.agent_id}",
                    embedder=OpenAIEmbedder(),
                )
            except Exception:
                return None
        return None

    def _overlap_score(self, query: str, text: str) -> float:
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not query_words:
            return 0.0
        return len(query_words & text_words) / len(query_words)

    async def retrieve(self, query: str, top_k: int | None = None) -> List[str]:
        limit = top_k or self._top_k

        if self._vdb is not None:
            try:
                docs = self._vdb.search(query, limit=limit)
                results = []
                for doc in docs:
                    content = doc.content if hasattr(doc, "content") else str(doc)
                    score = getattr(doc, "score", 1.0) or 1.0
                    if score >= self._score_threshold:
                        results.append(content)
                if results:
                    return results
            except Exception:
                pass

        with Session(get_engine()) as session:
            try:
                from pika.core.context import get_tenant_id

                tenant = self.tenant_id if self.tenant_id is not None else get_tenant_id()
            except Exception:
                tenant = self.tenant_id

            clauses = [
                AgentCorrection.agent_id == self.agent_id,
                AgentCorrection.active.is_(True),
            ]
            if tenant:
                clauses.append(AgentCorrection.tenant_id == tenant)
            rows = session.scalars(select(AgentCorrection).where(*clauses)).all()

        scored = [
            (self._overlap_score(query, f"{r.intent}: {r.correction}"), r)
            for r in rows
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            f"{r.intent}: {r.correction}"
            for score, r in scored[:limit]
            if score >= self._score_threshold
        ]

    async def add(self, intent: str, correction: str) -> AgentCorrection:
        try:
            from pika.core.context import get_tenant_id

            tenant = self.tenant_id if self.tenant_id is not None else get_tenant_id()
        except Exception:
            tenant = self.tenant_id
        with Session(get_engine()) as session:
            rec = AgentCorrection(
                agent_id=self.agent_id,
                tenant_id=tenant,
                intent=intent,
                correction=correction,
            )
            session.add(rec)
            session.commit()
            session.refresh(rec)

        if self._vdb is not None:
            try:
                from agno.knowledge.document.base import Document

                doc = Document(
                    id=str(rec.id),
                    content=f"{intent}: {correction}",
                    meta_data={"agent_id": self.agent_id},
                )
                self._vdb.insert(content_hash=str(rec.id), documents=[doc])
            except Exception:
                pass

        return rec

    async def promote(self, correction_id: int):
        with Session(get_engine()) as session:
            rec = session.get(AgentCorrection, correction_id)
            if rec:
                rec.promoted = True
                session.commit()

    async def deactivate(self, correction_id: int):
        with Session(get_engine()) as session:
            rec = session.get(AgentCorrection, correction_id)
            if rec:
                rec.active = False
                session.commit()

        if self._vdb is not None:
            try:
                self._vdb.delete_by_id(str(correction_id))
            except Exception:
                pass
