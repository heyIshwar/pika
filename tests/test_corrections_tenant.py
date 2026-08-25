"""Cross-tenant isolation of CorrectionStore (vector + SQL retrieval paths).

Regression tests for the vector-path leak: the SQL fallback filtered by
tenant_id while LanceDB retrieval returned other tenants' corrections.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from pika.corrections.models import AgentCorrection, Base
from pika.corrections.store import CorrectionStore


class FakeDoc:
    def __init__(self, content: str, meta: dict | None = None, score: float = 0.9):
        self.content = content
        self.meta_data = meta or {}
        self.score = score


class FilterIgnoringVDB:
    """Worst-case stand-in for LanceDb: 'forgets' to apply dict filters."""

    def __init__(self):
        self.docs: list[FakeDoc] = []
        self.searches: list[dict] = []

    def insert(self, content_hash, documents):
        self.docs.extend(documents)

    def delete_by_id(self, doc_id):
        self.docs = [d for d in self.docs if getattr(d, "id", None) != doc_id]

    def search(self, query, limit=5, filters=None):
        self.searches.append({"query": query, "limit": limit, "filters": filters})
        # Ignore filters entirely — isolation must survive this.
        return list(self.docs)[:limit]


@pytest.fixture()
def db_engine(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("pika.corrections.store.get_engine", lambda: engine)
    return engine


@pytest.fixture()
def no_vdb(monkeypatch):
    monkeypatch.setattr(CorrectionStore, "_init_vector_db", lambda self: None)


def _seed(engine, agent_id, tenant, intent, correction):
    with __import__("sqlalchemy").orm.Session(engine) as session:
        session.add(
            AgentCorrection(
                agent_id=agent_id, tenant_id=tenant, intent=intent, correction=correction
            )
        )
        session.commit()


# ---------- vector path ----------


def test_vector_retrieve_never_crosses_tenants(db_engine, no_vdb):
    store = CorrectionStore(agent_id="agent_a", tenant_id="acme")
    fake = FilterIgnoringVDB()
    fake.docs = [
        FakeDoc("greeting: say hi", meta={"agent_id": "agent_a", "tenant_id": "acme"}),
        FakeDoc(
            "greeting: leak rival secret",
            meta={"agent_id": "agent_a", "tenant_id": "rival"},
        ),
    ]
    store._vdb = fake

    import asyncio

    results = asyncio.run(store.retrieve("greeting"))

    assert results == ["greeting: say hi"]
    # Tenant filter was requested server-side too, with over-fetch headroom.
    call = fake.searches[0]
    assert call["filters"] == {"tenant_id": "acme"}
    assert call["limit"] == store._top_k * 4


def test_vector_retrieve_unfiltered_when_no_tenant(db_engine, no_vdb):
    store = CorrectionStore(agent_id="agent_a")
    fake = FilterIgnoringVDB()
    fake.docs = [FakeDoc("greeting: say hi"), FakeDoc("farewell: bye")]
    store._vdb = fake

    import asyncio

    results = asyncio.run(store.retrieve("greeting"))
    assert fake.searches[0]["filters"] is None
    # No tenant scope: legacy behavior — every indexed doc is eligible.
    assert sorted(results) == ["farewell: bye", "greeting: say hi"]


def test_add_stamps_tenant_into_vector_metadata(db_engine, no_vdb):
    import asyncio

    store = CorrectionStore(agent_id="agent_a", tenant_id="acme")
    fake = FilterIgnoringVDB()
    store._vdb = fake

    rec = asyncio.run(store.add("greeting", "say hi exactly once"))

    assert rec.tenant_id == "acme"
    assert fake.docs[0].meta_data["tenant_id"] == "acme"
    assert fake.docs[0].meta_data["agent_id"] == "agent_a"


# ---------- SQL path ----------


def test_sql_fallback_filters_by_tenant(db_engine, no_vdb):
    _seed(db_engine, "agent_a", "acme", "currency", "answer in EUR")
    _seed(db_engine, "agent_a", "rival", "currency", "answer in USD")

    import asyncio

    acme = asyncio.run(CorrectionStore(agent_id="agent_a", tenant_id="acme").retrieve("currency"))
    rival = asyncio.run(CorrectionStore(agent_id="agent_a", tenant_id="rival").retrieve("currency"))

    assert acme == ["currency: answer in EUR"]
    assert rival == ["currency: answer in USD"]


def test_tenant_from_request_context_when_unset(db_engine, no_vdb, monkeypatch):
    _seed(db_engine, "agent_a", "globex", "tone", "be formal")
    monkeypatch.setattr(
        "pika.core.context.get_tenant_id", lambda: "globex", raising=False
    )

    import asyncio

    results = asyncio.run(CorrectionStore(agent_id="agent_a").retrieve("tone"))
    assert results == ["tone: be formal"]
