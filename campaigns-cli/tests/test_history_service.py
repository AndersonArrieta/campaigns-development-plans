from datetime import datetime
from typing import Any

import boto3
import pytest

from campaigns_cli.services.dynamo_service import CampaignsTable, LogsTable
from campaigns_cli.services.history_service import (
    HistoryWindow,
    RowState,
    RowType,
    campaign_detail,
    classify_rows,
    load_history,
)
from tests.dynamo_fixtures import (
    CAMPAIGN_A,
    CAMPAIGN_B,
    CAMPAIGN_INDEX,
    CAMPAIGNS_TABLE,
    LOGS_TABLE,
    REGION,
    CallCounter,
    campaign_item,
    create_campaigns_table,
    create_logs_table,
    put_campaigns,
    seed_history,
)

NOW = datetime(2026, 10, 13, 18, 25)


def _row(notification_id: str, when: str, retries: str = "0") -> dict[str, Any]:
    return campaign_item(notification_id, when, retries=retries)


# --- classify_rows (sin AWS) ---


def test_classify_original_out_of_hours_and_retry_in_datetime_order() -> None:
    rows = [
        _row("n-1", "2026-10-14 09:00:00", "1"),
        _row("n-1", "2026-10-13 10:00:00"),
        _row("n-1", "2026-10-13 18:00:00"),
    ]

    [timeline] = classify_rows(rows, NOW)

    assert [row.datetime for row in timeline.rows] == [
        "2026-10-13 10:00:00",
        "2026-10-13 18:00:00",
        "2026-10-14 09:00:00",
    ]
    assert [row.tipo for row in timeline.rows] == [
        RowType.ORIGINAL,
        RowType.FUERA_DE_HORARIO,
        RowType.REINTENTO,
    ]
    assert timeline.rescheduled


def test_classify_state_with_fixed_clock() -> None:
    rows = [
        _row("pasada", "2026-10-13 17:00:00"),
        _row("en-curso", "2026-10-13 18:00:00"),
        _row("pendiente", "2026-10-13 19:00:00"),
    ]

    states = {t.notification_id: t.rows[0].estado for t in classify_rows(rows, NOW)}

    assert states == {
        "pasada": RowState.PASADA,
        "en-curso": RowState.EN_CURSO,
        "pendiente": RowState.PENDIENTE,
    }


def test_classify_compares_retries_as_integers() -> None:
    rows = [_row("n-1", "2026-10-13 10:00:00", "9"), _row("n-1", "2026-10-13 12:00:00", "10")]

    [timeline] = classify_rows(rows, NOW)

    assert timeline.rows[1].tipo is RowType.REINTENTO
    assert timeline.rows[1].retries == 10


def test_classify_groups_by_notification_and_sorts_timelines() -> None:
    rows = [_row("b", "2026-10-13 12:00:00"), _row("a", "2026-10-13 10:00:00")]

    timelines = classify_rows(rows, NOW)

    assert [t.notification_id for t in timelines] == ["a", "b"]
    assert not any(t.rescheduled for t in timelines)
    assert timelines[0].as_dict()["filas"] == [
        {
            "hora_colombia": "2026-10-13 10:00:00",
            "retries": 0,
            "tipo": RowType.ORIGINAL,
            "estado": RowState.PASADA,
        }
    ]


# --- Con moto ---


def _client() -> Any:
    return boto3.client("dynamodb", region_name=REGION)


@pytest.fixture
def seeded(mocked_aws: None) -> tuple[CampaignsTable, LogsTable]:
    create_campaigns_table()
    create_logs_table()
    seed_history()
    return CampaignsTable(_client(), CAMPAIGNS_TABLE), LogsTable(_client(), LOGS_TABLE)


def test_by_notification_returns_every_row(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    campaigns, _ = seeded

    result = campaigns.by_notification("n-1")

    assert result.scanned
    assert [item["datetime"] for item in result.items] == [
        "2026-10-13 10:00:00",
        "2026-10-13 18:00:00",
        "2026-10-14 09:00:00",
    ]


def test_by_campaigns_splits_in_batches_of_100(mocked_aws: None) -> None:
    create_campaigns_table()
    ids = [f"campaign-{index:03d}" for index in range(150)]
    put_campaigns(
        [
            campaign_item(f"n-{index:03d}", "2026-10-13 10:00:00", campaign_id=cid)
            for index, cid in enumerate(ids)
        ]
        + [campaign_item("ajena", "2026-10-13 10:00:00", campaign_id=CAMPAIGN_B)]
    )
    client = CallCounter(_client())

    result = CampaignsTable(client, CAMPAIGNS_TABLE).by_campaigns(ids)

    assert client.calls["scan"] == 2
    assert len(result.items) == 150
    assert {item["campaign_id"] for item in result.items} == set(ids)


def test_by_campaigns_without_ids_does_not_scan(mocked_aws: None) -> None:
    create_campaigns_table()
    client = CallCounter(_client())

    result = CampaignsTable(client, CAMPAIGNS_TABLE).by_campaigns([])

    assert result.items == []
    assert not result.scanned
    assert client.calls == {}


def test_all_rows_with_app_filter(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    campaigns, logs = seeded

    assert len(campaigns.all().items) == 5
    assert [item["notification_id"] for item in campaigns.all("otra-app").items] == ["n-4"]
    assert [item["app_id"] for item in logs.all().items] == ["otra-app", "UNKNOWN", "others-test"]
    by_app = logs.all("others-test")
    assert not by_app.scanned
    assert len(by_app.items) == 1
    assert logs.all(limit=1).truncated


def test_logs_by_campaign_includes_unknown(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    _, logs = seeded

    result = logs.by_campaign(CAMPAIGN_A)

    assert [item["app_id"] for item in result.items] == ["others-test", "UNKNOWN"]


def test_load_history_joins_loads_with_their_rows(
    seeded: tuple[CampaignsTable, LogsTable],
) -> None:
    campaigns, logs = seeded

    result = load_history(logs, campaigns, HistoryWindow(datetime(2026, 10, 13, 0)), NOW)

    summaries = {load.entry.app_id: load.summary() for load in result.loads}
    assert list(summaries) == ["otra-app", "UNKNOWN", "others-test"]
    success = summaries["others-test"]
    assert success["estado"] == "SUCCESSFUL"
    assert success["campaign_id"] == CAMPAIGN_A
    assert (success["filas"], success["notificaciones"], success["reprogramados"]) == (4, 2, 1)
    assert success["pendientes"] == 1  # n-1 del 14 a las 09:00; la de las 18:00 está EN_CURSO
    for failed in ("otra-app", "UNKNOWN"):
        assert summaries[failed]["filas"] == 0
        assert summaries[failed]["estado"] == "FAILED"
    assert result.scanned


def test_load_history_by_app(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    campaigns, logs = seeded

    result = load_history(
        logs, campaigns, HistoryWindow(datetime(2026, 10, 13, 0), app_id="otra-app"), NOW
    )

    assert [load.entry.app_id for load in result.loads] == ["otra-app"]
    assert result.loads[0].timelines == []
    assert not result.scanned  # query por app_id y ningún campaign_id con filas


def test_campaign_detail(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    campaigns, logs = seeded

    detail = campaign_detail(logs, campaigns, CAMPAIGN_A, NOW)

    assert detail.found
    assert [entry.app_id for entry in detail.loads] == ["others-test", "UNKNOWN"]
    # Misma hora original: se ordenan por usuario.
    assert [t.notification_id for t in detail.timelines] == ["n-2", "n-1"]
    assert detail.stats.as_dict() == {
        "usuarios": 2,
        "filas": 4,
        "notificaciones": 2,
        "reprogramados": 1,
        "fuera_de_horario": 1,
        "reintentos": 1,
        "pendientes": 1,
        "en_curso": 1,
    }
    data = detail.as_dict()
    assert data["notificaciones"][1]["filas"][2]["tipo"] == RowType.REINTENTO


def test_campaign_detail_with_index_queries(mocked_aws: None) -> None:
    create_campaigns_table(with_index=True)
    create_logs_table()
    seed_history()
    campaigns = CampaignsTable(_client(), CAMPAIGNS_TABLE, CAMPAIGN_INDEX)

    detail = campaign_detail(LogsTable(_client(), LOGS_TABLE), campaigns, CAMPAIGN_B, NOW)

    assert [t.notification_id for t in detail.timelines] == ["n-4"]


def test_campaign_detail_not_found(seeded: tuple[CampaignsTable, LogsTable]) -> None:
    campaigns, logs = seeded

    assert not campaign_detail(logs, campaigns, "no-existe", NOW).found
