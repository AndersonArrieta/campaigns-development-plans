import json

from typer.testing import CliRunner

from campaigns_cli.main import app

runner = CliRunner()

COMPLETE_RESOURCES = """
CAMPAIGNS_INPUT_BUCKET=bucket
CAMPAIGNS_TABLE_NAME=tabla
INGESTER_LAMBDA_NAME=ingester
SCHEDULER_LAMBDA_NAME=scheduler
CAMPAIGNS_LOG_GROUPS=/aws/lambda/ingester,/aws/lambda/scheduler
"""


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


def test_check_ok(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(COMPLETE_RESOURCES)

    result = runner.invoke(app, ["--output", "json", "config", "check"])

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["ok"] is True
    statuses = {row["variable"]: row["estado"] for row in report["variables"]}
    assert statuses["CAMPAIGNS_TABLE_CAMPAIGN_INDEX"] == "OPCIONAL"


def test_check_reports_missing_resources(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_INPUT_BUCKET=bucket\n")

    result = runner.invoke(app, ["--output", "json", "config", "check"])

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    missing = {row["variable"] for row in report["variables"] if row["estado"] == "FALTA CONFIG"}
    assert missing == {
        "CAMPAIGNS_TABLE_NAME",
        "INGESTER_LAMBDA_NAME",
        "SCHEDULER_LAMBDA_NAME",
        "CAMPAIGNS_LOG_GROUPS",
    }
