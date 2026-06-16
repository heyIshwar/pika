from dataclasses import dataclass, field
from typing import Any

from pika.testing.mocks import MockLLMProvider


@dataclass
class AgentTestHarness:
    agent_class: type
    mock_responses: list[str] = field(default_factory=list)

    async def run(self, message: str) -> Any:
        mock_llm = MockLLMProvider(responses=self.mock_responses, id="mock")
        agent = self.agent_class(model=mock_llm, enable_corrections=False, enable_cache=False)
        return await agent.run(message)

    async def assert_response_contains(self, message: str, expected: str):
        result = await self.run(message)
        content = result.content if hasattr(result, "content") else str(result)
        assert expected in content, f'Expected "{expected}" in response, got:\n{content}'
