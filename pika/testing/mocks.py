from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

from agno.models.base import Model
from agno.models.response import ModelResponse


@dataclass
class MockLLMProvider(Model):
    """Cycles through responses list for deterministic tests."""

    responses: list[str] = field(default_factory=list)
    _index: int = field(default=0, init=False, repr=False)

    def _next_content(self) -> str:
        if not self.responses:
            return "Mock response"
        content = self.responses[self._index % len(self.responses)]
        self._index += 1
        return content

    async def ainvoke(self, messages, **kwargs) -> ModelResponse:
        return ModelResponse(content=self._next_content())

    def invoke(self, messages, **kwargs) -> ModelResponse:
        return ModelResponse(content=self._next_content())

    def invoke_stream(self, messages, **kwargs) -> Iterator[ModelResponse]:
        yield self.invoke(messages, **kwargs)

    async def ainvoke_stream(self, messages, **kwargs) -> AsyncIterator[ModelResponse]:
        yield await self.ainvoke(messages, **kwargs)

    def _parse_provider_response(self, response: Any, **kwargs) -> ModelResponse:
        if isinstance(response, ModelResponse):
            return response
        return ModelResponse(content=str(response))

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        return self._parse_provider_response(response)
