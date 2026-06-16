from agno.team import Team

from pika.config.loader import get_config
from pika.infra.storage import get_storage


class BaseTeam(Team):
    """
    Extend this to create a multi-agent team.

    Example:
        class ResearchTeam(BaseTeam):
            team_id = 'research_team'
            members = [ResearchAgent(), WriterAgent()]
            mode = 'coordinate'
    """

    team_id: str = ""

    def __init__(self, **kwargs):
        if not self.team_id:
            raise ValueError("BaseTeam subclasses must set team_id")

        cfg = get_config("teams", self.team_id)
        db = get_storage()
        team_kwargs = cfg.get("team_kwargs", {})
        super().__init__(db=db, **team_kwargs, **kwargs)
