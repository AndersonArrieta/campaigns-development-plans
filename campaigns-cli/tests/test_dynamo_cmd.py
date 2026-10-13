import json
from datetime import datetime
from typing import Any

import pytest
from typer.testing import CliRunner

from campaigns_cli.commands import dynamo_cmd
from campaigns_cli.main import app
from tests.dynamo_fixtures import (
    CAMPAIGN_A,
    ENV,
    create_campaigns_table,
    create_logs_table,
    log_item,
    put_logs,
    seed_campaigns,
)

runner = CliRunner(env={"COLUMNS": "250"})

pytestmark = pytest.mark.usefixtures("mocked_aws")


@pytest.fixture
def tables(write_env, mocked_aws: None) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    create_campaigns_table()
    seed_campaigns()
    create_logs_table()
    put_logs(
        [
            log_item("others-test", "2026-10-13 14:00:00.100000", file_route="a.csv"),
            log_item("otra-app", "2026-10-13 15:00:00.300000", status="FAILED"),
        ]
    )


def _json(*args: str) -> tuple[int, Any, str]:
    result = runner.invoke(app, ["--output", "json", "dynamo", *args])
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result.exit_code, data, result.stderr


@pytest.mark.usefixtures("tables")
def test_get_with_datetime() -> None:
    code, data, stderr = _json("get", "--notification-id", "n-1", "--datetime", "2026-10-13 10")

    assert code == 0
    assert data["user"] == "573232540390"
    assert "scan" not in stderr


@pytest.mark.usefixtures("tables")
def test_get_without_datetime_warns_scan() -> None:
    code, data, stderr = _json("get", "--notification-id", "n-3")

    assert code == 0
    assert data["datetime"] == "2026-10-13 15:00:00"
    assert "scan" in stderr


@pytest.mark.usefixtures("tables")
def test_get_missing_exits_1() -> None:
    code, _, stderr = _json("get", "--notification-id", "nada")

    assert code == 1
    assert "nada" in stderr


@pytest.mark.usefixtures("tables")
def test_find_by_campaign_table_output() -> None:
    result = runner.invoke(app, ["dynamo", "find", "--campaign-id", CAMPAIGN_A])

    assert result.exit_code == 0
    assert "n-1" in result.stdout
    assert "3 registro(s)" in result.stderr


def test_find_requires_a_filter() -> None:
    result = runner.invoke(app, ["dynamo", "find"])

    assert result.exit_code == 2


@pytest.mark.usefixtures("tables")
def test_list_by_date() -> None:
    code, data, _ = _json("list", "--date", "2026-10-13")

    assert code == 0
    assert [item["notification_id"] for item in data] == ["n-1", "n-2", "n-3"]


@pytest.mark.usefixtures("tables")
def test_list_by_hour_and_range() -> None:
    _, by_hour, _ = _json("list", "--date", "2026-10-13", "--hour", "15")
    _, by_range, _ = _json("list", "--from", "2026-10-13 15:00", "--to", "2026-10-14 08:00")

    assert [item["notification_id"] for item in by_hour] == ["n-3"]
    assert [item["notification_id"] for item in by_range] == ["n-3", "n-4"]


@pytest.mark.usefixtures("tables")
def test_list_today_defaults_to_colombia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamo_cmd, "colombia_now", lambda: datetime(2026, 10, 14, 21, 0))

    code, data, _ = _json("list")

    assert code == 0
    assert [item["notification_id"] for item in data] == ["n-4"]


@pytest.mark.parametrize(
    "args",
    [
        ["--date", "2026-10-13", "--from", "2026-10-13", "--to", "2026-10-14"],
        ["--from", "2026-10-13"],
        ["--from", "2026-10-14", "--to", "2026-10-13"],
        ["--date", "13/10/2026"],
    ],
)
@pytest.mark.usefixtures("tables")
def test_list_usage_errors(args: list[str]) -> None:
    assert runner.invoke(app, ["dynamo", "list", *args]).exit_code == 2


def test_missing_table_setting_exits_2(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("")

    result = runner.invoke(app, ["dynamo", "list"])

    assert result.exit_code == 2
    assert "CAMPAIGNS_TABLE_NAME" in result.stderr


@pytest.mark.usefixtures("tables")
def test_logs_recent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamo_cmd, "utc_now", lambda: datetime(2026, 10, 13, 18, 0))

    code, data, _ = _json("logs", "--since", "6h")

    assert code == 0
    assert [entry["app_id"] for entry in data] == ["otra-app", "others-test"]
    assert data[1]["campaign_id"] == CAMPAIGN_A
    assert data[1]["archivo"] == "a.csv"
    assert data[0]["detalle_errores"][0]["error"] == "CSV structure validation failed"


@pytest.mark.usefixtures("tables")
def test_logs_since_excludes_older(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamo_cmd, "utc_now", lambda: datetime(2026, 10, 13, 18, 0))

    _, data, _ = _json("logs", "--since", "3h")

    assert [entry["app_id"] for entry in data] == ["otra-app"]


@pytest.mark.usefixtures("tables")
def test_logs_by_app_table_with_details() -> None:
    result = runner.invoke(
        app, ["dynamo", "logs", "--app-id", "otra-app", "--from", "2026-10-13", "--details"]
    )

    assert result.exit_code == 0
    assert "FAILED" in result.stdout
    assert "Detalle de errores" in result.stdout


@pytest.mark.usefixtures("tables")
def test_logs_follow(monkeypatch: pytest.MonkeyPatch) -> None:
    original = dynamo_cmd.follow_logs

    def bounded(*args: Any, **kwargs: Any) -> Any:
        return original(*args, **{**kwargs, "max_polls": 1})

    monkeypatch.setattr(dynamo_cmd, "follow_logs", bounded)

    result = runner.invoke(app, ["dynamo", "logs", "--follow", "--from", "2026-10-13 00:00"])

    assert result.exit_code == 0
    assert "Siguiendo cargas" in result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "others-test" in lines[0]
    assert "archivo=a.csv" in lines[0]


@pytest.mark.parametrize(
    "args",
    [
        ["--since", "1h", "--from", "2026-10-13"],
        ["--to", "2026-10-13"],
        ["--follow", "--from", "2026-10-13", "--to", "2026-10-14"],
        ["--since", "ayer"],
    ],
)
@pytest.mark.usefixtures("tables")
def test_logs_usage_errors(args: list[str]) -> None:
    assert runner.invoke(app, ["dynamo", "logs", *args]).exit_code == 2


@pytest.mark.usefixtures("tables")
def test_read_commands_allowed_in_prod(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_ENV=prod\n")

    result = runner.invoke(app, ["dynamo", "list", "--date", "2026-10-13"])

    assert result.exit_code == 0
