from datetime import datetime
from typing import Any

import boto3
import pytest
from botocore.stub import ANY, Stubber

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.services.logs_service import (
    LogsService,
    build_query,
    component_name,
)
from campaigns_cli.timeutils import colombia_to_epoch_ms

REGION = "us-east-1"
INGESTER = "/aws/lambda/nu0284001-artemis-plc-dev-campaigns-ingester-lambda"
SCHEDULER = "/aws/lambda/nu0284001-artemis-plc-dev-campaigns-scheduler-lambda"
START = datetime(2026, 10, 13, 8, 0)
END = datetime(2026, 10, 13, 12, 0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _row(timestamp: str, group: str, message: str) -> list[dict[str, str]]:
    return [
        {"field": "@timestamp", "value": timestamp},
        {"field": "@log", "value": f"123456789012:{group}"},
        {"field": "@logStream", "value": "2026/10/13/[$LATEST]abc"},
        {"field": "@message", "value": message},
        {"field": "@ptr", "value": "ptr"},
    ]


def _stubbed() -> tuple[Any, Stubber]:
    client = boto3.client(
        "logs", region_name=REGION, aws_access_key_id="x", aws_secret_access_key="x"
    )
    return client, Stubber(client)


def test_component_name() -> None:
    assert component_name(INGESTER) == "campaigns-ingester-lambda"
    assert component_name("/ecs/platform-campaigns-ms") == "platform-campaigns-ms"


def test_build_query_escapes_literal() -> None:
    query = build_query('abc"def', 10)

    assert 'like "abc\\"def"' in query
    assert "| limit 10" in query


def test_search_parses_results_in_colombia_time() -> None:
    client, stubber = _stubbed()
    stubber.add_response(
        "start_query",
        {"queryId": "q-1"},
        {
            "logGroupNames": [INGESTER, SCHEDULER],
            "startTime": colombia_to_epoch_ms(START) // 1000,
            "endTime": colombia_to_epoch_ms(END) // 1000,
            "queryString": ANY,
            "limit": 200,
        },
    )
    stubber.add_response(
        "get_query_results", {"status": "Running", "results": []}, {"queryId": "q-1"}
    )
    stubber.add_response(
        "get_query_results",
        {
            "status": "Complete",
            "results": [
                _row("2026-10-13 15:00:02.000", SCHEDULER, "Message Id n-1 sent\n"),
                _row("2026-10-13 14:00:01.500", INGESTER, "[Campaign c-1] notification_id=n-1"),
            ],
        },
        {"queryId": "q-1"},
    )
    clock = FakeClock()

    with stubber:
        result = LogsService(client, sleep=clock.sleep, clock=clock).search(
            [INGESTER, SCHEDULER], "n-1-xyz", START, END, limit=200, timeout=60, poll_interval=2
        )

    assert [hit.component for hit in result.hits] == [
        "campaigns-ingester-lambda",
        "campaigns-scheduler-lambda",
    ]
    assert result.hits[0].timestamp == datetime(2026, 10, 13, 9, 0, 1, 500000)
    assert result.hits[1].message == "Message Id n-1 sent"
    assert result.counts == {INGESTER: 1, SCHEDULER: 1}
    assert clock.sleeps == [2]


def test_search_reports_groups_without_hits() -> None:
    client, stubber = _stubbed()
    stubber.add_response("start_query", {"queryId": "q-1"})
    stubber.add_response(
        "get_query_results",
        {"status": "Complete", "results": [_row("2026-10-13 14:00:00.000", INGESTER, "x")]},
    )

    with stubber:
        result = LogsService(client).search(
            [INGESTER, SCHEDULER], "abcdef", START, END, limit=10, timeout=60, poll_interval=1
        )

    assert result.counts == {INGESTER: 1, SCHEDULER: 0}


def test_search_batches_more_than_50_groups() -> None:
    client, stubber = _stubbed()
    groups = [f"/aws/lambda/g{i}" for i in range(60)]
    for query_id, batch in (("q-1", groups[:50]), ("q-2", groups[50:])):
        stubber.add_response(
            "start_query",
            {"queryId": query_id},
            {
                "logGroupNames": batch,
                "startTime": ANY,
                "endTime": ANY,
                "queryString": ANY,
                "limit": 5,
            },
        )
        stubber.add_response("get_query_results", {"status": "Complete", "results": []})

    with stubber:
        result = LogsService(client).search(
            groups, "abcdef", START, END, limit=5, timeout=60, poll_interval=1
        )

    stubber.assert_no_pending_responses()
    assert len(result.counts) == 60


def test_search_timeout_stops_query() -> None:
    client, stubber = _stubbed()
    stubber.add_response("start_query", {"queryId": "q-1"})
    for _ in range(3):
        stubber.add_response("get_query_results", {"status": "Running", "results": []})
    stubber.add_response("stop_query", {"success": True}, {"queryId": "q-1"})
    clock = FakeClock()

    with stubber, pytest.raises(TestFailedError, match="no terminó en 10s"):
        LogsService(client, sleep=clock.sleep, clock=clock).search(
            [INGESTER], "abcdef", START, END, limit=10, timeout=10, poll_interval=5
        )

    stubber.assert_no_pending_responses()


def test_search_failed_query() -> None:
    client, stubber = _stubbed()
    stubber.add_response("start_query", {"queryId": "q-1"})
    stubber.add_response("get_query_results", {"status": "Failed", "results": []})

    with stubber, pytest.raises(TestFailedError, match="Failed"):
        LogsService(client).search(
            [INGESTER], "abcdef", START, END, limit=10, timeout=10, poll_interval=1
        )


@pytest.mark.parametrize("term", ["", "abc", "  abcde  "])
def test_search_rejects_short_terms(term: str) -> None:
    client, _ = _stubbed()

    with pytest.raises(UsageError, match="al menos"):
        LogsService(client).search(
            [INGESTER], term, START, END, limit=10, timeout=10, poll_interval=1
        )


# --- filter_log_events / describe_log_groups con moto ---


def _put_events(group: str, events: list[tuple[datetime, str]]) -> None:
    logs = boto3.client("logs", region_name=REGION)
    logs.create_log_group(logGroupName=group)
    logs.create_log_stream(logGroupName=group, logStreamName="stream-1")
    logs.put_log_events(
        logGroupName=group,
        logStreamName="stream-1",
        logEvents=[
            {"timestamp": colombia_to_epoch_ms(when), "message": message}
            for when, message in events
        ],
    )


@pytest.fixture
def scheduler_events(mocked_aws: None) -> LogsService:
    _put_events(
        SCHEDULER,
        [
            (datetime(2026, 10, 13, 9, 0, 1), "START RequestId: r-1"),
            (datetime(2026, 10, 13, 9, 0, 2), "Notifications found in DynamoDB: 2\n"),
            (datetime(2026, 10, 13, 9, 0, 3), "Message Id n-1 sent"),
            (datetime(2026, 10, 13, 10, 0, 1), "Notifications found in DynamoDB: 0"),
        ],
    )
    return LogsService(boto3.client("logs", region_name=REGION))


def test_events_in_window(scheduler_events: LogsService) -> None:
    hits, truncated = scheduler_events.events(
        SCHEDULER, datetime(2026, 10, 13, 9), datetime(2026, 10, 13, 9, 30)
    )

    assert not truncated
    assert [hit.message for hit in hits] == [
        "START RequestId: r-1",
        "Notifications found in DynamoDB: 2",
        "Message Id n-1 sent",
    ]
    assert hits[0].timestamp == datetime(2026, 10, 13, 9, 0, 1)


def test_events_with_filter(scheduler_events: LogsService) -> None:
    hits, _ = scheduler_events.events(
        SCHEDULER, datetime(2026, 10, 13), pattern="Notifications found"
    )

    assert len(hits) == 2


def test_events_limit_keeps_latest(scheduler_events: LogsService) -> None:
    hits, truncated = scheduler_events.events(SCHEDULER, datetime(2026, 10, 13), limit=2)

    assert truncated
    assert [hit.message for hit in hits] == [
        "Message Id n-1 sent",
        "Notifications found in DynamoDB: 0",
    ]


def test_follow_yields_only_new_events(mocked_aws: None) -> None:
    _put_events(SCHEDULER, [(datetime(2026, 10, 13, 9, 0, 1), "primero")])
    clock = FakeClock()
    service = LogsService(boto3.client("logs", region_name=REGION), sleep=clock.sleep)
    stream = service.follow(SCHEDULER, datetime(2026, 10, 13, 9), interval=3, max_polls=2)

    first = next(stream)
    boto3.client("logs", region_name=REGION).put_log_events(
        logGroupName=SCHEDULER,
        logStreamName="stream-1",
        logEvents=[
            {"timestamp": colombia_to_epoch_ms(datetime(2026, 10, 13, 9, 5)), "message": "nuevo"}
        ],
    )
    rest = list(stream)

    assert first.message == "primero"
    assert [hit.message for hit in rest] == ["nuevo"]
    assert clock.sleeps == [3]


def test_list_groups(mocked_aws: None) -> None:
    logs = boto3.client("logs", region_name=REGION)
    logs.create_log_group(logGroupName=INGESTER)
    logs.create_log_group(logGroupName=SCHEDULER)
    logs.create_log_group(logGroupName="/aws/lambda/otra")
    logs.put_retention_policy(logGroupName=INGESTER, retentionInDays=30)

    groups = LogsService(logs).list_groups("/aws/lambda/nu0284001")

    assert [group["log_group"] for group in groups] == [INGESTER, SCHEDULER]
    assert groups[0]["retencion_dias"] == 30
