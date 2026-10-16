from datetime import UTC, datetime, timedelta

import boto3
import pytest
from botocore.exceptions import ReadTimeoutError

from campaigns_cli.services.dynamo_service import CampaignsTable
from campaigns_cli.services.lambda_service import LambdaService
from campaigns_cli.services.logs_service import LogsService
from campaigns_cli.services.scheduler_service import (
    Outcome,
    SchedulerService,
    current_partition,
    health_ok,
    outcome_of,
)
from campaigns_cli.timeutils import colombia_to_epoch_ms
from tests.dynamo_fixtures import (
    CAMPAIGNS_TABLE,
    REGION,
    campaign_item,
    create_campaigns_table,
    put_campaigns,
)
from tests.scheduler_fixtures import (
    SCHEDULER,
    SCHEDULER_LOG_GROUP,
    FakeLambda,
    scheduler_payload,
)

# 2026-10-15 03:30 UTC = 2026-10-14 22:30 en Colombia.
FIXED_NOW = datetime(2026, 10, 15, 3, 30, tzinfo=UTC)
PARTITION = "2026-10-14 22:00:00"


def test_current_partition_uses_colombia_hour() -> None:
    assert current_partition(FIXED_NOW) == PARTITION
    assert current_partition(datetime(2026, 10, 15, 3, 30)) == PARTITION  # sin zona = UTC
    assert current_partition(datetime(2026, 10, 15, 5, 0, tzinfo=UTC)) == "2026-10-15 00:00:00"


def _service(
    fake: FakeLambda, *, clock: object = None, logs: LogsService | None = None
) -> SchedulerService:
    table = CampaignsTable(boto3.client("dynamodb", region_name=REGION), CAMPAIGNS_TABLE)
    return SchedulerService(
        LambdaService(fake, fake.factory, sleep=lambda _: None),  # type: ignore[arg-type]
        SCHEDULER,
        table=table,
        logs=logs,
        log_group=SCHEDULER_LOG_GROUP,
        clock=clock or (lambda: FIXED_NOW),  # type: ignore[arg-type]
    )


@pytest.mark.usefixtures("mocked_aws")
def test_preview_counts_by_app_and_flags_other_apps() -> None:
    create_campaigns_table()
    put_campaigns(
        [
            campaign_item("n-1", PARTITION),
            campaign_item("n-2", PARTITION, user="573001112233"),
            campaign_item("n-3", PARTITION, app_id="otra-app"),
            campaign_item("n-4", "2026-10-14 23:00:00"),
        ]
    )

    preview = _service(FakeLambda()).preview()

    assert preview.partition == PARTITION
    assert preview.by_app == {"others-test": 2, "otra-app": 1}
    assert preview.total == 3
    assert preview.other_apps == ["otra-app"]


@pytest.mark.usefixtures("mocked_aws")
def test_run_invokes_with_empty_event() -> None:
    create_campaigns_table()
    fake = FakeLambda()
    service = _service(fake)

    result = service.run(service.preview(), tail=False)

    assert fake.payloads == [{}]
    assert fake.calls[0]["InvocationType"] == "RequestResponse"
    assert result.outcome is Outcome.OK
    assert not result.partition_changed


@pytest.mark.usefixtures("mocked_aws")
def test_run_detects_partition_change() -> None:
    create_campaigns_table()
    moments = iter([FIXED_NOW + timedelta(minutes=29, seconds=59), FIXED_NOW + timedelta(hours=1)])
    service = _service(FakeLambda(), clock=lambda: next(moments))

    result = service.run(service.preview(), tail=False)

    assert result.partition_changed
    assert result.partition_at_invoke == "2026-10-14 23:00:00"


@pytest.mark.usefixtures("mocked_aws")
def test_unknown_result_looks_for_execution_result_in_logs() -> None:
    create_campaigns_table()
    logs_client = boto3.client("logs", region_name=REGION)
    logs_client.create_log_group(logGroupName=SCHEDULER_LOG_GROUP)
    logs_client.create_log_stream(logGroupName=SCHEDULER_LOG_GROUP, logStreamName="s1")
    fake = FakeLambda()
    fake.queue = [ReadTimeoutError(endpoint_url="https://lambda")]
    service = _service(fake, logs=LogsService(logs_client))
    service.lambdas.clock = lambda: datetime(2026, 10, 14, 22, 30)
    logs_client.put_log_events(
        logGroupName=SCHEDULER_LOG_GROUP,
        logStreamName="s1",
        logEvents=[
            {
                "timestamp": colombia_to_epoch_ms(datetime(2026, 10, 14, 22, 20)),
                "message": "Execution result: anterior",
            },
            {
                "timestamp": colombia_to_epoch_ms(datetime(2026, 10, 14, 22, 31)),
                "message": "Execution result: {'total': 2}",
            },
        ],
    )

    result = service.run(service.preview(), tail=False)

    assert result.outcome is Outcome.DESCONOCIDO
    assert len(fake.calls) == 1
    assert [hit.message for hit in result.log_hits] == ["Execution result: {'total': 2}"]


def test_outcome_and_health_rules() -> None:
    fake = FakeLambda()
    fake.queue = [
        scheduler_payload(total=3, failed=1),
        ({"errorMessage": "boom"}, "Unhandled"),
        {"statusCode": 500, "message": "Kafka caído"},
        {"statusCode": 200, "message": "ok"},
    ]
    lambdas = LambdaService(fake, fake.factory)  # type: ignore[arg-type]

    failed = lambdas.invoke_once(SCHEDULER, {}, tail=False)
    crashed = lambdas.invoke_once(SCHEDULER, {}, tail=False)
    kafka_down = lambdas.invoke_once(SCHEDULER, {"type": "health"}, tail=False)
    kafka_up = lambdas.invoke_once(SCHEDULER, {"type": "health"}, tail=False)

    assert outcome_of(failed) is Outcome.FALLA
    assert outcome_of(crashed) is Outcome.FALLA
    assert not health_ok(crashed)
    assert not health_ok(kafka_down)
    assert health_ok(kafka_up)
    assert fake.read_timeouts == [330] * 4
