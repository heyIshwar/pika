import pytest

from agents.research_agent.agent import ResearchAgent
from pika.testing.harness import AgentTestHarness


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
