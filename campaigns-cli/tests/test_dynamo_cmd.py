import json
from datetime import datetime
from typing import Any

import pytest
from botocore.client import BaseClient
from typer.testing import CliRunner

from campaigns_cli.commands import dynamo_cmd
from campaigns_cli.main import app
from campaigns_cli.services.clean_service import CleanPlan, CleanResult, TableResult
from tests.dynamo_fixtures import (
    CAMPAIGN_A,
    CAMPAIGNS_TABLE,
    ENV,
    LOGS_TABLE,
    campaign_item,
    count_items,
    create_campaigns_table,
    create_logs_table,
    log_item,
    put_campaigns,
    put_logs,
    seed_campaigns,
    seed_history,
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
    assert [row["datetime"] for row in data] == ["2026-10-13 15:00:00"]
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
def test_list_hour_without_date_uses_today_colombia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamo_cmd, "colombia_now", lambda: datetime(2026, 10, 14, 21, 0))

    code, data, _ = _json("list", "--hour", "8")

    assert code == 0
    assert [item["notification_id"] for item in data] == ["n-4"]


@pytest.mark.usefixtures("history_tables")
def test_list_without_dates_returns_both_tables() -> None:
    code, data, stderr = _json("list")
    result = runner.invoke(app, ["dynamo", "list"])

    assert code == 0
    assert set(data) == {"campaigns", "logs"}
    assert (len(data["campaigns"]), len(data["logs"])) == (5, 3)
    assert "scan" in stderr
    assert result.exit_code == 0
    assert "Tabla de campañas" in result.stdout
    assert "Tabla de logs" in result.stdout


@pytest.mark.usefixtures("history_tables")
def test_list_without_dates_filters_and_limits() -> None:
    _, by_app, _ = _json("list", "--app-id", "otra-app")
    _, limited, stderr = _json("list", "-n", "1")

    assert [item["notification_id"] for item in by_app["campaigns"]] == ["n-4"]
    assert [item["app_id"] for item in by_app["logs"]] == ["otra-app"]
    assert (len(limited["campaigns"]), len(limited["logs"])) == (1, 1)
    assert "primeros 1" in stderr


@pytest.mark.usefixtures("history_tables")
def test_list_without_dates_user_filters_only_campaigns() -> None:
    _, data, _ = _json("list", "--user", "573001112233")

    assert [item["notification_id"] for item in data["campaigns"]] == ["n-2"]
    assert len(data["logs"]) == 3


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


# --- purge ---


@pytest.mark.usefixtures("tables")
def test_purge_with_yes_deletes_test_app_only() -> None:
    put_campaigns([campaign_item("ajeno", "2026-10-13 10:00:00", app_id="otra-app")])

    result = runner.invoke(
        app, ["--yes", "--output", "json", "dynamo", "purge", "--campaign-id", CAMPAIGN_A]
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "campaign_id": CAMPAIGN_A,
        "app_id": "others-test",
        "borrados": 3,
        "omitidos": 1,
        "fallidos": 0,
    }
    assert "otra-app" not in result.stdout
    assert "Se omiten 1" in result.stderr
    assert count_items(CAMPAIGNS_TABLE) == 2  # "ajeno" y n-4 de CAMPAIGN_B
    assert count_items(LOGS_TABLE) == 2  # la tabla de logs no se toca


@pytest.mark.usefixtures("tables")
def test_purge_rejected_deletes_nothing() -> None:
    result = runner.invoke(app, ["dynamo", "purge", "--campaign-id", CAMPAIGN_A], input="n\n")

    assert result.exit_code == 0
    assert "Operación cancelada" in result.stderr
    assert count_items(CAMPAIGNS_TABLE) == 4


@pytest.mark.usefixtures("tables")
def test_purge_confirmed_deletes() -> None:
    result = runner.invoke(app, ["dynamo", "purge", "--campaign-id", CAMPAIGN_A], input="y\n")

    assert result.exit_code == 0
    assert "Borrados" in result.stdout
    assert count_items(CAMPAIGNS_TABLE) == 1


@pytest.mark.usefixtures("tables")
def test_purge_without_rows_does_not_ask() -> None:
    result = runner.invoke(app, ["dynamo", "purge", "--campaign-id", "no-existe"])

    assert result.exit_code == 0
    assert "No hay registros que borrar" in result.stderr


@pytest.mark.usefixtures("tables")
def test_purge_blocked_in_prod(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_ENV=prod\n")

    result = runner.invoke(app, ["--yes", "dynamo", "purge", "--campaign-id", CAMPAIGN_A])

    assert result.exit_code == 2
    assert "no está permitido en prod" in result.stderr
    assert count_items(CAMPAIGNS_TABLE) == 4


# --- T-020: get con reprogramaciones, history, campaign, dump y clean ---

HISTORY_NOW = datetime(2026, 10, 13, 18, 25)


@pytest.fixture
def history_tables(write_env, mocked_aws: None, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    create_campaigns_table()
    create_logs_table()
    seed_history()
    monkeypatch.setattr(dynamo_cmd, "colombia_now", lambda: HISTORY_NOW)
    monkeypatch.setattr(dynamo_cmd, "utc_now", lambda: datetime(2026, 10, 13, 20, 0))


@pytest.fixture
def aws_operations(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Registra las operaciones que la CLI envía a AWS."""
    calls: list[str] = []
    original = BaseClient._make_api_call

    def spy(self: BaseClient, operation_name: str, api_params: Any) -> Any:
        calls.append(operation_name)
        return original(self, operation_name, api_params)

    monkeypatch.setattr(BaseClient, "_make_api_call", spy)
    return calls


@pytest.mark.usefixtures("history_tables")
def test_get_without_datetime_returns_every_rescheduled_row() -> None:
    code, data, stderr = _json("get", "--notification-id", "n-1")

    assert code == 0
    assert [(row["datetime"], row["tipo"], row["estado"]) for row in data] == [
        ("2026-10-13 10:00:00", "ORIGINAL", "PASADA"),
        ("2026-10-13 18:00:00", "FUERA_DE_HORARIO", "EN_CURSO"),
        ("2026-10-14 09:00:00", "REINTENTO", "PENDIENTE"),
    ]
    assert "scan" in stderr


@pytest.mark.usefixtures("history_tables")
def test_get_rescheduled_table_output() -> None:
    result = runner.invoke(app, ["dynamo", "get", "--notification-id", "n-1"])

    assert result.exit_code == 0
    assert "3 filas" in result.stdout
    assert "REINTENTO" in result.stdout


@pytest.mark.usefixtures("history_tables")
def test_history_lines_with_counts() -> None:
    code, data, _ = _json("history", "--since", "12h")

    assert code == 0
    by_app = {line["app_id"]: line for line in data}
    assert list(by_app) == ["otra-app", "UNKNOWN", "others-test"]
    success = by_app["others-test"]
    assert success["estado"] == "SUCCESSFUL"
    assert (success["filas"], success["notificaciones"]) == (4, 2)
    assert (success["reprogramados"], success["pendientes"]) == (1, 1)
    assert by_app["otra-app"]["estado"] == "FAILED"
    assert by_app["otra-app"]["filas"] == 0
    assert by_app["otra-app"]["detalle_errores"][0]["error"] == "CSV structure validation failed"


@pytest.mark.usefixtures("history_tables")
def test_history_by_app_table_with_details() -> None:
    result = runner.invoke(
        app, ["dynamo", "history", "--app-id", "otra-app", "--from", "2026-10-13", "--details"]
    )

    assert result.exit_code == 0
    assert "Historial de cargas" in result.stdout
    assert "Detalle de errores" in result.stdout


@pytest.mark.usefixtures("history_tables")
def test_history_rejects_since_and_from() -> None:
    assert (
        runner.invoke(app, ["dynamo", "history", "--since", "1h", "--from", "2026-10-13"]).exit_code
        == 2
    )


@pytest.mark.usefixtures("history_tables")
def test_campaign_json() -> None:
    code, data, _ = _json("campaign", "--campaign-id", CAMPAIGN_A)

    assert code == 0
    assert [load["app_id"] for load in data["cargas"]] == ["others-test", "UNKNOWN"]
    assert data["resumen"]["reprogramados"] == 1
    n1 = next(n for n in data["notificaciones"] if n["notification_id"] == "n-1")
    assert [row["tipo"] for row in n1["filas"]] == ["ORIGINAL", "FUERA_DE_HORARIO", "REINTENTO"]


@pytest.mark.usefixtures("history_tables")
def test_campaign_table_shows_rescheduled_notifications_and_summary() -> None:
    result = runner.invoke(app, ["dynamo", "campaign", "--campaign-id", CAMPAIGN_A])

    assert result.exit_code == 0
    assert "Notificación n-1" in result.stdout
    assert "Notificación n-2" not in result.stdout
    assert "Resumen" in result.stdout


@pytest.mark.usefixtures("history_tables")
def test_campaign_not_found_exits_1() -> None:
    assert runner.invoke(app, ["dynamo", "campaign", "--campaign-id", "nada"]).exit_code == 1


@pytest.mark.usefixtures("history_tables")
def test_dump_all_json() -> None:
    code, data, stderr = _json("dump")

    assert code == 0
    assert set(data) == {"campaigns", "logs"}
    assert (len(data["campaigns"]), len(data["logs"])) == (5, 3)
    assert "scan" in stderr


@pytest.mark.usefixtures("history_tables")
def test_dump_one_table_filtered_and_table_output() -> None:
    code, data, _ = _json("dump", "--table", "logs", "--app-id", "otra-app")
    result = runner.invoke(app, ["dynamo", "dump"])

    assert code == 0
    assert list(data) == ["logs"]
    assert [item["app_id"] for item in data["logs"]] == ["otra-app"]
    assert result.exit_code == 0
    assert "Tabla de campañas" in result.stdout
    assert "Tabla de logs" in result.stdout


@pytest.mark.usefixtures("history_tables")
def test_clean_yes_empties_both_tables() -> None:
    code, data, stderr = _json_yes("clean")

    assert code == 0
    assert [row["restantes"] for row in data["resultado"]] == [0, 0]
    assert data["plan"]["tablas"][0]["por_app_id"] == {"otra-app": 1, "others-test": 4}
    assert "EN_CURSO" in stderr
    assert count_items(CAMPAIGNS_TABLE) == 0
    assert count_items(LOGS_TABLE) == 0


@pytest.mark.usefixtures("history_tables")
def test_clean_only_logs() -> None:
    code, _, _ = _json_yes("clean", "--table", "logs")

    assert code == 0
    assert count_items(LOGS_TABLE) == 0
    assert count_items(CAMPAIGNS_TABLE) == 5


@pytest.mark.usefixtures("history_tables")
def test_clean_by_campaign() -> None:
    result = runner.invoke(app, ["--yes", "dynamo", "clean", "--campaign-id", CAMPAIGN_A])

    assert result.exit_code == 0
    assert "Plan de borrado" in result.stdout
    assert "Resultado de dynamo clean" in result.stdout
    assert count_items(CAMPAIGNS_TABLE) == 1
    assert count_items(LOGS_TABLE) == 1


@pytest.mark.usefixtures("history_tables")
def test_clean_dry_run_does_not_call_batch_write(aws_operations: list[str]) -> None:
    code, data, stderr = _json_yes("clean", "--dry-run")

    assert code == 0
    assert data["resultado"] is None
    assert "BatchWriteItem" not in aws_operations
    assert "no se borró nada" in stderr
    assert count_items(CAMPAIGNS_TABLE) == 5


@pytest.mark.usefixtures("history_tables")
def test_clean_does_not_ask_for_confirmation() -> None:
    # Sin --yes y sin entrada: si pidiera confirmación, abortaría sin borrar.
    result = runner.invoke(app, ["dynamo", "clean"], input="")

    assert result.exit_code == 0, result.stderr
    assert "¿Borrar" not in result.stderr
    assert "Borrando 8 fila(s) (vaciado completo)" in result.stderr
    assert count_items(CAMPAIGNS_TABLE) == 0
    assert count_items(LOGS_TABLE) == 0


@pytest.mark.usefixtures("history_tables")
def test_clean_with_remaining_rows_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def leave_one(plan: CleanPlan) -> CleanResult:
        return CleanResult([TableResult("campaigns", CAMPAIGNS_TABLE, 4, 0, 1)])

    monkeypatch.setattr(dynamo_cmd, "execute", leave_one)

    result = runner.invoke(app, ["--yes", "dynamo", "clean", "--table", "campaigns"])

    assert result.exit_code == 1
    assert "1 restante(s)" in result.stderr


@pytest.mark.usefixtures("history_tables")
def test_prod_blocks_clean_but_allows_reads(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_ENV=prod\n")

    assert runner.invoke(app, ["--yes", "dynamo", "clean"]).exit_code == 2
    assert count_items(CAMPAIGNS_TABLE) == 5
    for args in (
        ["history", "--since", "12h"],
        ["campaign", "--campaign-id", CAMPAIGN_A],
        ["dump"],
        ["get", "--notification-id", "n-1"],
    ):
        assert runner.invoke(app, ["dynamo", *args]).exit_code == 0, args


def _json_yes(*args: str) -> tuple[int, Any, str]:
    result = runner.invoke(app, ["--yes", "--output", "json", "dynamo", *args])
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result.exit_code, data, result.stderr
