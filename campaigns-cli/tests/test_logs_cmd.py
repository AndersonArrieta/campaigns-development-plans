import json
from datetime import datetime
from typing import Any

import boto3
import pytest
from typer.testing import CliRunner

from campaigns_cli.commands import logs_cmd
from campaigns_cli.main import app
from campaigns_cli.services.logs_service import LogsService
from campaigns_cli.timeutils import colombia_to_epoch_ms

runner = CliRunner(env={"COLUMNS": "250"})

REGION = "us-east-1"
INGESTER_NAME = "nu0284001-artemis-plc-dev-campaigns-ingester-lambda"
SCHEDULER_NAME = "nu0284001-artemis-plc-dev-campaigns-scheduler-lambda"
INGESTER = f"/aws/lambda/{INGESTER_NAME}"
SCHEDULER = f"/aws/lambda/{SCHEDULER_NAME}"
NOW = datetime(2026, 10, 13, 10, 0)

ENV = f"""
AWS_REGION={REGION}
INGESTER_LAMBDA_NAME={INGESTER_NAME}
SCHEDULER_LAMBDA_NAME={SCHEDULER_NAME}
"""


@pytest.fixture
def lambda_logs(write_env, mocked_aws: None, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    monkeypatch.setattr(logs_cmd, "colombia_now", lambda: NOW)
    logs = boto3.client("logs", region_name=REGION)
    for group, events in (
        (
            INGESTER,
            [(datetime(2026, 10, 13, 9, 50), "[Campaign c-1] Stored 2 notification(s)")],
        ),
        (
            SCHEDULER,
            [
                (datetime(2026, 10, 13, 9, 0, 1), "Notifications found in DynamoDB: 2"),
                (datetime(2026, 10, 13, 9, 55), "[red]Message Id n-1 sent[/red]"),
            ],
        ),
    ):
        logs.create_log_group(logGroupName=group)
        logs.create_log_stream(logGroupName=group, logStreamName="s")
        logs.put_log_events(
            logGroupName=group,
            logStreamName="s",
            logEvents=[
                {"timestamp": colombia_to_epoch_ms(when), "message": msg} for when, msg in events
            ],
        )


@pytest.mark.usefixtures("lambda_logs")
def test_groups_lists_lambda_log_groups() -> None:
    result = runner.invoke(app, ["--output", "json", "logs", "groups"])

    assert result.exit_code == 0
    assert [row["log_group"] for row in json.loads(result.stdout)] == [INGESTER, SCHEDULER]


@pytest.mark.usefixtures("lambda_logs")
def test_tail_scheduler_last_15_minutes() -> None:
    result = runner.invoke(app, ["logs", "tail", "--lambda", "scheduler"])

    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "[red]Message Id n-1 sent[/red]" in lines[0]


@pytest.mark.usefixtures("lambda_logs")
def test_tail_with_since_filter_and_json() -> None:
    result = runner.invoke(
        app,
        [
            "--output",
            "json",
            "logs",
            "tail",
            "-l",
            "scheduler",
            "--since",
            "2h",
            "--filter",
            "Notifications",
        ],
    )

    assert result.exit_code == 0
    events = json.loads(result.stdout)
    assert [event["mensaje"] for event in events] == ["Notifications found in DynamoDB: 2"]
    assert events[0]["hora"] == "2026-10-13 09:00:01.000"


@pytest.mark.usefixtures("lambda_logs")
def test_tail_by_group_and_range() -> None:
    result = runner.invoke(
        app,
        [
            "--output",
            "json",
            "logs",
            "tail",
            "-g",
            INGESTER,
            "--from",
            "2026-10-13 09:00",
            "--to",
            "2026-10-13 10:00",
        ],
    )

    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 1


@pytest.mark.usefixtures("lambda_logs")
def test_tail_without_events() -> None:
    result = runner.invoke(app, ["logs", "tail", "-l", "ingester", "--since", "1m"])

    assert result.exit_code == 0
    assert "Sin eventos" in result.stderr


@pytest.mark.usefixtures("lambda_logs")
def test_tail_follow(monkeypatch: pytest.MonkeyPatch) -> None:
    original = LogsService.follow

    def bounded(self: LogsService, *args: Any, **kwargs: Any) -> Any:
        return original(self, *args, **{**kwargs, "max_polls": 1})

    monkeypatch.setattr(LogsService, "follow", bounded)

    result = runner.invoke(app, ["logs", "tail", "-l", "scheduler", "-f", "--since", "2h"])

    assert result.exit_code == 0
    assert "Siguiendo" in result.stderr
    assert len([line for line in result.stdout.splitlines() if line.strip()]) == 2


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-l", "scheduler", "-g", SCHEDULER],
        ["-l", "scheduler", "--since", "1h", "--from", "2026-10-13"],
        ["-l", "scheduler", "--to", "2026-10-13"],
        ["-l", "scheduler", "-f", "--from", "2026-10-13", "--to", "2026-10-13 09:00"],
        ["-l", "otra"],
    ],
)
@pytest.mark.usefixtures("lambda_logs")
def test_tail_usage_errors(args: list[str]) -> None:
    assert runner.invoke(app, ["logs", "tail", *args]).exit_code == 2


def test_tail_lambda_not_configured(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(f"INGESTER_LAMBDA_NAME={INGESTER_NAME}\n")

    result = runner.invoke(app, ["logs", "tail", "-l", "scheduler"])

    assert result.exit_code == 2
    assert "SCHEDULER_LAMBDA_NAME" in result.stderr


# --- search: la consulta a Logs Insights se reemplaza (moto no la soporta bien) ---


def _row(timestamp: str, group: str, message: str) -> list[dict[str, str]]:
    return [
        {"field": "@timestamp", "value": timestamp},
        {"field": "@log", "value": f"123456789012:{group}"},
        {"field": "@logStream", "value": "s"},
        {"field": "@message", "value": message},
    ]


@pytest.fixture
def insights(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    rows = [_row("2026-10-13 14:50:00.000", INGESTER, "[Campaign c-1] notification_id=n-123456")]

    def fake_run_query(self: LogsService, groups: list[str], term: str, *args: Any) -> list[Any]:
        calls.append({"groups": groups, "term": term, "start": args[0], "end": args[1]})
        return [
            row for row in rows if any(f["value"].endswith(group) for f in row for group in groups)
        ]

    monkeypatch.setattr(LogsService, "_run_query", fake_run_query)
    return calls


@pytest.mark.usefixtures("lambda_logs")
def test_search_derives_lambda_groups(insights: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["--output", "json", "logs", "search", "--id", "n-123456"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert insights[0]["groups"] == [INGESTER, SCHEDULER]
    assert insights[0]["start"] == datetime(2026, 10, 12, 10, 0)
    assert data["hits"][0]["componente"] == "campaigns-ingester-lambda"
    assert data["hits"][0]["hora"] == "2026-10-13 09:50:00.000"
    assert {row["log_group"]: row["coincidencias"] for row in data["resumen"]} == {
        INGESTER: 1,
        SCHEDULER: 0,
    }


@pytest.mark.usefixtures("lambda_logs")
def test_search_table_marks_components_without_hits(insights: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["logs", "search", "--id", "n-123456", "--since", "2h"])

    assert result.exit_code == 0
    assert "campaigns-ingester-lambda" in result.stdout
    assert "✗ 0" in result.stdout


@pytest.mark.usefixtures("lambda_logs")
def test_search_only_one_lambda(insights: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["logs", "search", "--id", "n-123456", "-l", "scheduler"])

    assert insights[0]["groups"] == [SCHEDULER]
    assert result.exit_code == 1
    assert "no aparece" in result.stderr


@pytest.mark.usefixtures("lambda_logs")
def test_search_log_groups_setting_wins(
    write_env,
    insights: list[dict[str, Any]],  # type: ignore[no-untyped-def]
) -> None:
    write_env(ENV + "CAMPAIGNS_LOG_GROUPS=/ecs/platform-campaigns-ms\n")

    runner.invoke(app, ["logs", "search", "--id", "n-123456"])

    assert insights[0]["groups"] == ["/ecs/platform-campaigns-ms"]


def test_search_without_groups(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("")

    result = runner.invoke(app, ["logs", "search", "--id", "n-123456"])

    assert result.exit_code == 2
    assert "CAMPAIGNS_LOG_GROUPS" in result.stderr
