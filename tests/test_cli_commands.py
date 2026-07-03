from typer.testing import CliRunner

from pika.cli.main import cli
from pika.cli.aliases import COMMAND_ALIASES, ENTRYPOINT_ALIASES
from pika.cli.commands.loader import get_default_agent_id, resolve_agent_id

runner = CliRunner()


def test_chu_help():
    result = runner.invoke(cli, ["chu", "--help"])
    assert result.exit_code == 0
    assert "pika chu" in result.stdout
    assert "orchestrator" in result.stdout


def test_choo_help():
    result = runner.invoke(cli, ["choo", "--help"])
    assert result.exit_code == 0
    assert "pika choo" in result.stdout
    assert "orchestrator" in result.stdout


def test_default_agent_is_orchestrator():
    assert get_default_agent_id() == "orchestrator"


def test_resolve_agent_id():
    assert resolve_agent_id(None) == "orchestrator"
    assert resolve_agent_id("getting_started") == "getting_started"


def test_subcommand_aliases_registered():
    assert COMMAND_ALIASES["chu"] == ["pikachu"]
    assert COMMAND_ALIASES["choo"] == ["pikachoo"]
    assert "picka" not in COMMAND_ALIASES
    result = runner.invoke(cli, ["pikachu", "--help"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["pikachoo", "--help"])
    assert result.exit_code == 0


def test_entrypoint_aliases_map_to_chu_choo():
    assert ENTRYPOINT_ALIASES["pikachu"] == "chu"
    assert ENTRYPOINT_ALIASES["pikachoo"] == "choo"
    assert ENTRYPOINT_ALIASES["pika-chu"] == "chu"
    assert ENTRYPOINT_ALIASES["pika-choo"] == "choo"
    assert "picka" not in ENTRYPOINT_ALIASES
