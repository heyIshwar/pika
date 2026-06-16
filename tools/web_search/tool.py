from agno.tools import tool as agno_tool

from pika.tool import BaseTool


class WebSearchTool(BaseTool):
    tool_id = "web_search"

    @agno_tool(description="Search the web for a query")
    async def search(self, query: str) -> str:
        return f"Search results for: {query} (stub — wire real search provider here)"
