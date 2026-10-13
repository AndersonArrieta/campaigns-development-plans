from typer.testing import CliRunner

from campaigns_cli import __version__
from campaigns_cli.main import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Pruebas sobre los recursos AWS" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
