"""WebSearchSkill — bundles the WebSearchTool into a reusable skill."""
from pika.core.skill import BaseSkill


class WebSearchSkill(BaseSkill):
    skill_id = "web_search"
    description = "Can search the web and return a summary of results"

    def get_tools(self):
        from skills.web_search.tool import WebSearchTool

        t = WebSearchTool()
        return [t.search]
