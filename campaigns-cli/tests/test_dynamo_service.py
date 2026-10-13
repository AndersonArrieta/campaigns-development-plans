import json
from datetime import datetime
from typing import Any

import boto3
import pytest

from campaigns_cli.errors import UsageError
from campaigns_cli.services.dynamo_service import (
    MAX_HOURS,
    CampaignsTable,
    LogsTable,
    follow_logs,
    parse_log_entry,
)
from tests.dynamo_fixtures import (
    CAMPAIGN_A,
    CAMPAIGN_B,
    CAMPAIGN_INDEX,
    CAMPAIGNS_TABLE,
    LOGS_TABLE,
    REGION,
    campaign_item,
    create_campaigns_table,
    create_logs_table,
    log_item,
    put_campaigns,
    put_logs,
    seed_campaigns,
)

pytestmark = pytest.mark.usefixtures("mocked_aws")


def _client() -> Any:
    return boto3.client("dynamodb", region_name=REGION)


@pytest.fixture
def campaigns() -> CampaignsTable:
    create_campaigns_table()
    seed_campaigns()
    return CampaignsTable(_client(), CAMPAIGNS_TABLE)


@pytest.fixture
def logs() -> LogsTable:
    create_logs_table()
    put_logs(
        [
            log_item("others-test", "2026-10-13 14:00:00.100000", file_route="a.csv"),
            log_item("others-test", "2026-10-13 16:30:00.200000", file_route="b.csv"),
            log_item(
                "otra-app", "2026-10-13 15:00:00.300000", status="FAILED", campaign_id=CAMPAIGN_B
            ),
            log_item("others-test", "2026-10-12 09:00:00.000000", file_route="viejo.csv"),
        ]
    )
    return LogsTable(_client(), LOGS_TABLE)


# --- Tabla de campañas ---


def test_get_with_datetime_uses_key(campaigns: CampaignsTable) -> None:
    result = campaigns.get("n-1", "2026-10-13 10:00:00")

    assert not result.scanned
    item = result.items[0]
    assert item["notification_id"] == "n-1"
    assert item["context"] == {"text": "hola"}
    assert item["expiration_date"] == 1760500000


def test_get_without_datetime_scans(campaigns: CampaignsTable) -> None:
    result = campaigns.get("n-3")

    assert result.scanned
    assert result.items[0]["datetime"] == "2026-10-13 15:00:00"


def test_get_missing(campaigns: CampaignsTable) -> None:
    assert campaigns.get("no-existe", "2026-10-13 10:00:00").items == []
    assert campaigns.get("no-existe").items == []


def test_find_by_campaign_scans_and_sorts(campaigns: CampaignsTable) -> None:
    result = campaigns.find(campaign_id=CAMPAIGN_A)

    assert result.scanned
    assert [item["notification_id"] for item in result.items] == ["n-2", "n-1", "n-3"]


def test_find_combines_filters(campaigns: CampaignsTable) -> None:
    result = campaigns.find(campaign_id=CAMPAIGN_A, user="573001112233")

    assert [item["notification_id"] for item in result.items] == ["n-2"]


def test_find_by_app_id(campaigns: CampaignsTable) -> None:
    assert [i["notification_id"] for i in campaigns.find(app_id="otra-app").items] == ["n-4"]


def test_find_with_limit_is_truncated(campaigns: CampaignsTable) -> None:
    result = campaigns.find(campaign_id=CAMPAIGN_A, limit=2)

    assert len(result.items) == 2
    assert result.truncated


def test_find_uses_index_when_configured() -> None:
    create_campaigns_table(with_index=True)
    seed_campaigns()
    table = CampaignsTable(_client(), CAMPAIGNS_TABLE, CAMPAIGN_INDEX)

    result = table.find(campaign_id=CAMPAIGN_A)

    assert not result.scanned
    assert len(result.items) == 3


def test_scan_follows_pagination() -> None:
    create_campaigns_table()
    put_campaigns(
        [
            campaign_item(f"n-{i:04d}", "2026-10-13 10:00:00", user=f"57300{i:07d}")
            for i in range(1200)
        ]
    )
    table = CampaignsTable(_client(), CAMPAIGNS_TABLE)

    result = table.find(campaign_id=CAMPAIGN_A, limit=5000)

    assert len(result.items) == 1200
    assert not result.truncated


def test_list_range_queries_each_hour(campaigns: CampaignsTable) -> None:
    result = campaigns.list_range(datetime(2026, 10, 13, 0), datetime(2026, 10, 13, 23))

    assert not result.scanned
    assert [item["notification_id"] for item in result.items] == ["n-1", "n-2", "n-3"]


def test_list_range_single_hour_and_filters(campaigns: CampaignsTable) -> None:
    hour = datetime(2026, 10, 13, 10, 30)

    assert len(campaigns.list_range(hour, hour).items) == 2
    filtered = campaigns.list_range(hour, hour, user="573232540390")
    assert [item["notification_id"] for item in filtered.items] == ["n-1"]


def test_list_range_across_days(campaigns: CampaignsTable) -> None:
    result = campaigns.list_range(datetime(2026, 10, 13, 15), datetime(2026, 10, 14, 8))

    assert [item["notification_id"] for item in result.items] == ["n-3", "n-4"]


def test_list_range_rejects_huge_ranges(campaigns: CampaignsTable) -> None:
    with pytest.raises(UsageError, match=str(MAX_HOURS)):
        campaigns.list_range(datetime(2026, 1, 1), datetime(2026, 12, 31))


# --- Tabla de logs ---


def test_parse_successful_log_entry() -> None:
    entry = parse_log_entry(log_item("others-test", "2026-10-13 14:00:00.1", file_route="x.csv"))

    assert entry.status == "SUCCESSFUL"
    assert entry.campaign_id == CAMPAIGN_A
    assert entry.file == "x.csv"
    assert (entry.total, entry.successful, entry.omitted, entry.errors) == (2, 2, 0, 0)
    assert entry.error_details == []


def test_parse_failed_log_entry() -> None:
    entry = parse_log_entry(log_item("otra-app", "2026-10-13 15:00:00", status="FAILED"))

    assert entry.status == "FAILED"
    assert entry.campaign_id == CAMPAIGN_A
    assert entry.errors == 2
    assert entry.error_details[0]["error"] == "CSV structure validation failed"


@pytest.mark.parametrize("result", [None, "no es json", json.dumps(["lista"])])
def test_parse_log_entry_tolerates_bad_result(result: Any) -> None:
    item = {"app_id": "x", "datetime": "2026-10-13 15:00:00"}
    if result is not None:
        item["result"] = result

    entry = parse_log_entry(item)

    assert entry.status == "?"
    assert entry.campaign_id is None


def test_logs_by_app_newest_first(logs: LogsTable) -> None:
    result = logs.by_app("others-test")

    assert [item["datetime"][:19] for item in result.items] == [
        "2026-10-13 16:30:00",
        "2026-10-13 14:00:00",
        "2026-10-12 09:00:00",
    ]


def test_logs_by_app_with_window_includes_last_second(logs: LogsTable) -> None:
    result = logs.by_app("others-test", datetime(2026, 10, 13, 0), datetime(2026, 10, 13, 16, 30))

    assert len(result.items) == 2


def test_logs_recent_across_apps(logs: LogsTable) -> None:
    result = logs.recent(datetime(2026, 10, 13, 0))

    assert result.scanned
    assert [item["app_id"] for item in result.items] == ["others-test", "otra-app", "others-test"]


def test_logs_recent_with_limit(logs: LogsTable) -> None:
    result = logs.recent(datetime(2026, 10, 1), limit=2)

    assert len(result.items) == 2
    assert result.truncated


def test_follow_logs_yields_only_new_entries() -> None:
    batches = [
        [log_item("a", "2026-10-13 10:00:00.1")],
        [log_item("a", "2026-10-13 10:00:00.1"), log_item("b", "2026-10-13 10:00:05.2")],
        [],
    ]
    requested: list[datetime] = []
    sleeps: list[float] = []

    def fetch(since: datetime) -> list[dict[str, Any]]:
        requested.append(since)
        return batches[len(requested) - 1]

    entries = list(
        follow_logs(fetch, datetime(2026, 10, 13, 9), interval=3, sleep=sleeps.append, max_polls=3)
    )

    assert [entry.app_id for entry in entries] == ["a", "b"]
    assert requested[0] == datetime(2026, 10, 13, 9)
    assert requested[2] == datetime(2026, 10, 13, 10, 0, 5)
    assert sleeps == [3, 3]
