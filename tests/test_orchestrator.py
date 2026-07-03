import pytest

from pika.cli.commands.loader import list_team_ids, load_agent


def test_orchestrator_in_registry():
    assert "orchestrator" in list_team_ids()


def test_orchestrator_loads_members(monkeypatch):
    pytest.importorskip("agno")

    class FakeResult:
        content = "ok"

    class FakeAgent:
        def __init__(self, agent_id: str):
            self.agent_id = agent_id

        async def run(self, message: str):
            return FakeResult()

    def fake_load(agent_id: str):
        if agent_id == "orchestrator":
            raise AssertionError("should not recurse into orchestrator")
        return FakeAgent(agent_id)

    monkeypatch.setattr("pika.orchestration.orchestrator.load_agent", fake_load)

    team = load_agent("orchestrator")
    assert team.agent_id == "orchestrator"
    assert len(team.members) == 2
