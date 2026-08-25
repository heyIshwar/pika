import pytest

from agents.research_agent.agent import ResearchAgent
from pika.testing.harness import AgentTestHarness


@pytest.fixture(autouse=True)
def _database_tool_config(monkeypatch):
    """ResearchAgent ships a DatabaseSkill; DatabaseTool now refuses to start
    without an explicit `db_url` (control-plane guard). Point it at in-memory
    SQLite for these tests."""
    monkeypatch.setattr(
        "pika.core.tool.get_config",
        lambda section, key: {"db_url": "sqlite:///:memory:"},
    )


@pytest.fixture
def harness():
    return AgentTestHarness(
        agent_class=ResearchAgent,
        mock_responses=[
            "Gold is trading at $3,200/oz. Source: kitco.com",
        ],
    )


@pytest.mark.asyncio
async def test_gold_price_query(harness):
    await harness.assert_response_contains(
        message="What is the price of gold?",
        expected="kitco.com",
    )


@pytest.mark.asyncio
async def test_response_not_empty(harness):
    result = await harness.run("Tell me about AI")
    assert result.content
    assert len(result.content) > 10
