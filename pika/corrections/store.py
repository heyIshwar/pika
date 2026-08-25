from __future__ import annotations

import logging
import os
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from pika.config.loader import get_config
from pika.corrections.models import AgentCorrection, init_corrections_db
from pika.infra.db import get_engine

logger = logging.getLogger(__name__)


class CorrectionStore:
    """SQL-backed correction store with optional LanceDB semantic search.

    Corrections are scoped per (agent_id, tenant_id). The tenant is resolved
    once per call from the explicit constructor arg or the request context,
    and is enforced on BOTH the vector and SQL retrieval paths.
    """

    def __init__(self, agent_id: str, tenant_id: str | None = None):
        init_corrections_db()
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        cfg = get_config("agents", agent_id).get("corrections", {})
        self._top_k = cfg.get("top_k", 5)
        self._score_threshold = cfg.get("score_threshold", 0.75)
        # Embedder for the semantic index: corrections config > knowledge
        # config > openai. Must match what indexed the rows — switching
        # embedders requires re-adding corrections.
        knowledge_cfg = get_config("agents", agent_id).get("knowledge") or {}
        self._embedder_name = (
            cfg.get("embedder") or knowledge_cfg.get("embedder") or "openai"
        )
        self._vdb = self._init_vector_db()

    def _resolve_tenant(self) -> str | None:
        if self.tenant_id is not None:
            return self.tenant_id
        try:
            from pika.core.context import get_tenant_id

            return get_tenant_id()
        except Exception:
            return None

    def _init_vector_db(self):
        if self._embedder_name == "openai" and not os.getenv("OPENAI_API_KEY"):
            logger.debug(
                "corrections[%s]: OPENAI_API_KEY unset; semantic index disabled",
                self.agent_id,
            )
            return None
        try:
            from agno.vectordb.lancedb import LanceDb
            from pika.config.loader import get_settings
            from pika.infra.db import get_embedder

            return LanceDb(
                uri=get_settings().get("vectordb", {}).get("path", ".lance"),
                table_name=f"corrections_{self.agent_id}",
                embedder=get_embedder(self._embedder_name),
            )
        except Exception:
            logger.warning(
                "corrections[%s]: could not initialize vector index; "
                "falling back to SQL-only mode",
                self.agent_id,
                exc_info=True,
            )
            return None

    def _overlap_score(self, query: str, text: str) -> float:
        def tokens(s: str) -> set[str]:
            # Strip punctuation so "currency" matches the "currency:" intent prefix.
            return {w.strip(" :,;.'\"()") for w in s.lower().split()} - {""}

        query_words = tokens(query)
        text_words = tokens(text)
        if not query_words:
            return 0.0
        return len(query_words & text_words) / len(query_words)

    @staticmethod
    def _doc_tenant(doc) -> Optional[str]:
        meta = getattr(doc, "meta_data", None) or {}
        return meta.get("tenant_id")

    async def retrieve(self, query: str, top_k: int | None = None) -> List[str]:
        limit = top_k or self._top_k
        tenant = self._resolve_tenant()

        if self._vdb is not None:
            try:
                # Agno applies dict filters as a post-retrieval metadata check,
                # so over-fetch before filtering or another tenant's rows can
                # crowd out this tenant's matches in the top-limit window.
                fetch = limit * 4 if tenant else limit
                filters = {"tenant_id": tenant} if tenant else None
                docs = self._vdb.search(query, limit=fetch, filters=filters)
                results = []
                for doc in docs:
                    # Defense in depth: never trust that the backend honored
                    # the filter — verify the tag ourselves as well.
                    if tenant and self._doc_tenant(doc) != tenant:
                        continue
                    content = doc.content if hasattr(doc, "content") else str(doc)
                    score = getattr(doc, "score", 1.0) or 1.0
                    if score >= self._score_threshold:
                        results.append(content)
                results = results[:limit]
                if results:
                    return results
            except Exception:
                logger.warning(
                    "corrections[%s]: vector search failed; falling back to SQL",
                    self.agent_id,
                    exc_info=True,
                )

        with Session(get_engine()) as session:
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
        tenant = self._resolve_tenant()
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
                    meta_data={"agent_id": self.agent_id, "tenant_id": tenant},
                )
                self._vdb.insert(content_hash=str(rec.id), documents=[doc])
            except Exception:
                # SQL row was written; only the semantic index failed. Surface it.
                logger.warning(
                    "corrections[%s]: vector insert failed for correction %s",
                    self.agent_id,
                    rec.id,
                    exc_info=True,
                )

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
                logger.warning(
                    "corrections[%s]: vector delete failed for correction %s",
                    self.agent_id,
                    correction_id,
                    exc_info=True,
                )
