from datetime import datetime
from typing import Any

import boto3
import pytest

from campaigns_cli.services.clean_service import TableChoice, execute, plan_clean
from campaigns_cli.services.dynamo_service import CampaignsTable, LogsTable
from tests.dynamo_fixtures import (
    CAMPAIGN_A,
    CAMPAIGN_B,
    CAMPAIGN_C,
    CAMPAIGN_INDEX,
    CAMPAIGNS_TABLE,
    LOGS_TABLE,
    REGION,
    CallCounter,
    FlakyBatchClient,
    campaign_item,
    count_items,
    create_campaigns_table,
    create_logs_table,
    log_item,
    put_campaigns,
    put_logs,
    seed_history,
)

pytestmark = pytest.mark.usefixtures("mocked_aws")

NOW = datetime(2026, 10, 13, 18, 25)


def _client() -> Any:
    return boto3.client("dynamodb", region_name=REGION)


def _no_sleep(_: float) -> None:
    return None


@pytest.fixture
def seeded(mocked_aws: None) -> None:
    """seed_history más 40 filas y 30 cargas de otra campaña: más de 25 por tabla."""
    create_campaigns_table()
    create_logs_table()
    seed_history()
    put_campaigns(
        [
            campaign_item(
                f"c-{i:03d}", "2026-10-15 10:00:00", campaign_id=CAMPAIGN_C, user=f"57300{i:07d}"
            )
            for i in range(40)
        ]
    )
    put_logs(
        [
            log_item("tercera-app", f"2026-10-12 10:00:{i:02d}.000000", campaign_id=CAMPAIGN_C)
            for i in range(30)
        ]
    )


def _tables(client: Any = None) -> tuple[CampaignsTable, LogsTable]:
    client = client or _client()
    return CampaignsTable(client, CAMPAIGNS_TABLE), LogsTable(client, LOGS_TABLE)


def _campaign_ids() -> set[str]:
    items = _client().scan(TableName=CAMPAIGNS_TABLE)["Items"]
    return {item["campaign_id"]["S"] for item in items}


@pytest.mark.usefixtures("seeded")
def test_full_clean_empties_both_tables() -> None:
    campaigns, logs = _tables()
    plan = plan_clean(campaigns, logs, NOW)

    result = execute(plan, sleep=_no_sleep)

    assert result.ok
    assert [(t.table, t.deleted, t.failed, t.remaining) for t in result.tables] == [
        ("campaigns", 45, 0, 0),
        ("logs", 33, 0, 0),
    ]
    assert count_items(CAMPAIGNS_TABLE) == 0
    assert count_items(LOGS_TABLE) == 0


@pytest.mark.usefixtures("seeded")
def test_plan_counts_by_app_rescheduled_and_pending() -> None:
    campaigns, logs = _tables()

    plan = plan_clean(campaigns, logs, NOW)

    campaigns_plan, logs_plan = plan.tables
    assert campaigns_plan.by_app == {"otra-app": 1, "others-test": 44}
    assert campaigns_plan.rescheduled == 2
    # n-1 del 14, n-4 del 14 y las 40 del 15 están por enviarse; n-1 de las 18:00 está en curso.
    assert (campaigns_plan.pending, campaigns_plan.in_progress) == (42, 1)
    assert logs_plan.by_app == {"UNKNOWN": 1, "otra-app": 1, "others-test": 1, "tercera-app": 30}
    assert plan.total == 78
    assert plan.in_progress == 1
    assert plan.scanned
    assert plan.as_dict()["tablas"][0]["reprogramadas"] == 2


@pytest.mark.usefixtures("seeded")
def test_clean_only_logs_keeps_campaigns() -> None:
    _, logs = _tables()
    before = count_items(CAMPAIGNS_TABLE)

    result = execute(plan_clean(None, logs, NOW), sleep=_no_sleep)

    assert result.ok
    assert [t.table for t in result.tables] == ["logs"]
    assert count_items(LOGS_TABLE) == 0
    assert count_items(CAMPAIGNS_TABLE) == before


@pytest.mark.usefixtures("seeded")
def test_clean_by_campaign_deletes_rescheduled_rows_and_unknown_load() -> None:
    campaigns, logs = _tables()

    plan = plan_clean(campaigns, logs, NOW, campaign_id=CAMPAIGN_A)
    result = execute(plan, sleep=_no_sleep)

    assert result.ok
    assert [(t.deleted, t.remaining) for t in result.tables] == [(4, 0), (2, 0)]
    assert _campaign_ids() == {CAMPAIGN_B, CAMPAIGN_C}
    remaining_logs = LogsTable(_client(), LOGS_TABLE).all().items
    assert "UNKNOWN" not in {item["app_id"] for item in remaining_logs}
    assert len(remaining_logs) == 31


def test_clean_by_campaign_with_index() -> None:
    create_campaigns_table(with_index=True)
    create_logs_table()
    seed_history()
    client = CallCounter(_client())
    campaigns = CampaignsTable(client, CAMPAIGNS_TABLE, CAMPAIGN_INDEX)

    plan = plan_clean(campaigns, None, NOW, campaign_id=CAMPAIGN_A)
    result = execute(plan, sleep=_no_sleep)

    assert not plan.scanned
    assert "scan" not in client.calls
    assert result.tables[0].deleted == 4
    assert _campaign_ids() == {CAMPAIGN_B}


@pytest.mark.usefixtures("seeded")
def test_rows_of_other_campaign_are_rechecked_before_deleting() -> None:
    campaigns, _ = _tables()
    plan = plan_clean(campaigns, None, NOW, campaign_id=CAMPAIGN_A)
    # Una fila ajena que se colara en el plan no se borra.
    plan.tables[0].rows.append(
        {"datetime": "2026-10-14 08:00:00", "notification_id": "n-4", "campaign_id": CAMPAIGN_B}
    )

    result = execute(plan, sleep=_no_sleep)

    assert result.tables[0].deleted == 4
    assert CAMPAIGN_B in _campaign_ids()


@pytest.mark.usefixtures("seeded")
def test_row_written_during_clean_is_reported_as_remaining() -> None:
    def concurrent_write() -> None:
        put_campaigns([campaign_item("tardía", "2026-10-16 10:00:00", campaign_id=CAMPAIGN_A)])

    client = CallCounter(_client(), after_batch=concurrent_write)
    campaigns, _ = _tables(client)

    result = execute(plan_clean(campaigns, None, NOW, campaign_id=CAMPAIGN_A), sleep=_no_sleep)

    assert not result.ok
    assert (result.tables[0].deleted, result.tables[0].remaining) == (4, 1)
    assert result.as_dicts()[0]["restantes"] == 1


@pytest.mark.usefixtures("seeded")
def test_unprocessed_items_are_retried_until_deleted() -> None:
    client = FlakyBatchClient(_client(), failures=3)
    campaigns, logs = _tables(client)

    result = execute(plan_clean(campaigns, logs, NOW), sleep=_no_sleep)

    assert result.ok
    assert count_items(CAMPAIGNS_TABLE) == 0
    assert count_items(LOGS_TABLE) == 0
    assert client.batch_calls > 4  # 2 lotes por tabla más los reintentos


def test_empty_tables_plan_nothing() -> None:
    create_campaigns_table()
    create_logs_table()
    campaigns, logs = _tables()

    plan = plan_clean(campaigns, logs, NOW)
    result = execute(plan, sleep=_no_sleep)

    assert plan.total == 0
    assert result.ok


def test_table_choice() -> None:
    assert TableChoice.ALL.includes_campaigns and TableChoice.ALL.includes_logs
    assert TableChoice.CAMPAIGNS.includes_campaigns and not TableChoice.CAMPAIGNS.includes_logs
    assert TableChoice.LOGS.includes_logs and not TableChoice.LOGS.includes_campaigns
