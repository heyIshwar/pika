"""DatabaseSkill — bundles the DatabaseTool into a reusable skill.

Gives an agent a live agentic interface to an existing SQL database: list
tables, describe schema, and (opt-in) run read-only SQL.

Requires `db_url` in config/tools/database.yaml, or explicit
`allow_control_plane_db: true` to use pika's own DATABASE_URL (not recommended).
`enable_run_sql_query` defaults to false; when enabled, only SELECT/WITH/SHOW/
DESCRIBE/EXPLAIN are allowed.
"""
from pika.core.skill import BaseSkill


class DatabaseSkill(BaseSkill):
    skill_id = "database"
    description = (
        "Can list tables and describe schema against a configured database; "
        "run_sql_query is opt-in and read-only"
    )

    def get_tools(self):
        from skills.database.tool import DatabaseTool

        t = DatabaseTool()
        tools = [t.list_tables, t.describe_table]
        if getattr(t, "_enable_run_sql", False):
            tools.append(t.run_sql_query)
        return tools
