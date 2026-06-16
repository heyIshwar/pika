from typer.testing import CliRunner

from pika.cli import cli

runner = CliRunner()


def test_chu_help():
    result = runner.invoke(cli, ["chu", "--help"])
    assert result.exit_code == 0
    assert "pika chu" in result.stdout


def test_choo_help():
    result = runner.invoke(cli, ["choo", "--help"])
    assert result.exit_code == 0
    assert "pika choo" in result.stdout


def test_chu_requires_agent_id():
    result = runner.invoke(cli, ["chu"])
    assert result.exit_code != 0


def test_choo_requires_agent_id():
    result = runner.invoke(cli, ["choo"])
    assert result.exit_code != 0
