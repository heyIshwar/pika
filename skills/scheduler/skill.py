"""Expose Agno SchedulerTools when AgentOS scheduler is enabled."""
from __future__ import annotations

from pika.core.skill import BaseSkill


class SchedulerSkill(BaseSkill):
    skill_id = "scheduler"
    description = "Create and manage recurring agent schedules (cron) via Agno SchedulerTools"

    def get_tools(self):
        from agno.tools.scheduler import SchedulerTools

        from pika.config.loader import get_settings
        from pika.infra.storage import get_storage

        settings = get_settings()
        sched = settings.get("scheduler") or {}
        tz = sched.get("default_timezone", "Asia/Kolkata")
        default_agent = settings.get("default_agent", "orchestrator")
        t = SchedulerTools(
            db=get_storage(),
            default_endpoint=f"/agents/{default_agent}/runs",
            default_timezone=tz,
        )
        return [
            t.create_schedule,
            t.list_schedules,
            t.get_schedule,
            t.delete_schedule,
            t.enable_schedule,
            t.disable_schedule,
            t.get_schedule_runs,
        ]
