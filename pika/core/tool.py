from pika.config.loader import get_config
from pika.observability.tracing import get_tracer


class BaseTool:
    """
    Extend this and decorate methods with @agno_tool.

    Example:
        class WebSearchTool(BaseTool):
            tool_id = 'web_search'

            @agno_tool(description='Search the web')
            async def search(self, query: str) -> str:
                ...
    """

    tool_id: str = ""

    def __init__(self):
        if not self.tool_id:
            raise ValueError("BaseTool subclasses must set tool_id")
        self._cfg = get_config("tools", self.tool_id)
        self._tracer = get_tracer(self.tool_id)
