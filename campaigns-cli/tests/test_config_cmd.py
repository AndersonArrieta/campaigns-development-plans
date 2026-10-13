import json

from typer.testing import CliRunner

from campaigns_cli.main import app

runner = CliRunner()


def test_show_table(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_ENV=qa\nCAMPAIGNS_TABLE_NAME=tabla-qa\n")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "CAMPAIGNS_ENV" in result.output
    assert "tabla-qa" in result.output


def test_show_json_with_sources(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_TABLE_NAME=tabla\n")

    result = runner.invoke(app, ["--output", "json", "config", "show"])

    assert result.exit_code == 0
    rows = {row["variable"]: row for row in json.loads(result.stdout)}
    assert rows["CAMPAIGNS_TABLE_NAME"] == {
        "variable": "CAMPAIGNS_TABLE_NAME",
        "valor": "tabla",
        "origen": ".env",
    }
    assert rows["CAMPAIGNS_ENV"]["origen"] == "default"


def test_cli_output_from_env_file(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CLI_OUTPUT=json\n")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert isinstance(json.loads(result.stdout), list)


def test_show_works_without_resources() -> None:
    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0


def test_show_with_custom_env_file(write_env) -> None:  # type: ignore[no-untyped-def]
    path = write_env("CAMPAIGNS_ENV=prod\n", name=".env.prod")

    result = runner.invoke(app, ["--env-file", str(path), "--output", "json", "config", "show"])

    assert result.exit_code == 0
    rows = {row["variable"]: row for row in json.loads(result.stdout)}
    assert rows["CAMPAIGNS_ENV"] == {
        "variable": "CAMPAIGNS_ENV",
        "valor": "prod",
        "origen": ".env.prod",
    }


def test_missing_env_file_is_usage_error() -> None:
    result = runner.invoke(app, ["--env-file", "inexistente.env", "config", "show"])

    assert result.exit_code == 2


def test_invalid_env_file_is_usage_error(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_ENV=staging\n")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 2
    assert "CAMPAIGNS_ENV" in result.stderr


def test_invalid_env_file_does_not_break_version(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_ENV=staging\n")

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0


def test_show_masks_aws_credentials(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("AWS_ACCESS_KEY_ID=AKIAEJEMPLO123\nAWS_SECRET_ACCESS_KEY=muysecretovalor\n")

    result = runner.invoke(app, ["--output", "json", "config", "show"])

    assert result.exit_code == 0
    assert "muysecretovalor" not in result.stdout
    assert "AKIAEJEMPLO123" not in result.stdout
    rows = {row["variable"]: row["valor"] for row in json.loads(result.stdout)}
    assert rows["AWS_SECRET_ACCESS_KEY"] == "mu****or"
