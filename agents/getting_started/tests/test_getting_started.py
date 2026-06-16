import pytest

from agents.getting_started.agent import GettingStartedAgent
from pika.testing.harness import AgentTestHarness


@pytest.fixture
def harness():
    return AgentTestHarness(
        agent_class=GettingStartedAgent,
        mock_responses=["Hi! I'm a getting started agent. How can I help?"],
    )


@pytest.mark.asyncio
async def test_basic(harness):
    result = await harness.run("Hello")
    assert result.content


@pytest.mark.asyncio
async def test_response_not_empty(harness):
    result = await harness.run("Tell me about pika")
    assert len(result.content) > 5
