"""DatabaseSkill — bundles the DatabaseTool into a reusable skill.

Gives an agent a live agentic interface to an existing SQL database: list
tables, describe schema, and run read queries. Defaults to pika's own
configured database; point it at a different existing database via
config/tools/database.yaml (db_url / schema).
"""
from pika.core.skill import BaseSkill


class DatabaseSkill(BaseSkill):
    skill_id = "database"
    description = "Can list tables, describe schema, and run SQL queries against the configured database"

    def get_tools(self):
        from skills.database.tool import DatabaseTool

        t = DatabaseTool()
        return [t.list_tables, t.describe_table, t.run_sql_query]
