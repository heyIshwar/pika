from pika.core.tool import BaseTool


class DatabaseTool(BaseTool):
    """Exposes an existing SQL database (schema + queries) to agents via agno.tools.sql.SQLTools."""

    tool_id = "database"

    def __init__(self):
        super().__init__()
        from agno.tools.sql import SQLTools

        db_url = self._cfg.get("db_url")
        if db_url:
            self._sql = SQLTools(db_url=db_url, schema=self._cfg.get("schema"))
        else:
            from pika.infra.db import get_engine

            self._sql = SQLTools(db_engine=get_engine(), schema=self._cfg.get("schema"))

        self.list_tables = self._sql.list_tables
        self.describe_table = self._sql.describe_table
        self.run_sql_query = self._sql.run_sql_query
