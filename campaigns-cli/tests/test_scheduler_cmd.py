import json
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ReadTimeoutError
from typer.testing import CliRunner

from campaigns_cli.aws import AwsClients
from campaigns_cli.main import app
from campaigns_cli.services import scheduler_service
from tests.dynamo_fixtures import ENV, campaign_item, create_campaigns_table, put_campaigns
from tests.scheduler_fixtures import (
    SCHEDULER,
    SCHEDULER_LOG_GROUP,
    FakeLambda,
    client_error,
    scheduler_payload,
)

runner = CliRunner(env={"COLUMNS": "250"})

FIXED_NOW = datetime(2026, 10, 15, 3, 30, tzinfo=UTC)
PARTITION = "2026-10-14 22:00:00"
SCHEDULER_ENV = f"{ENV}\nSCHEDULER_LAMBDA_NAME={SCHEDULER}\n"

pytestmark = pytest.mark.usefixtures("mocked_aws")


@pytest.fixture
def fake_lambda(write_env, monkeypatch: pytest.MonkeyPatch) -> FakeLambda:  # type: ignore[no-untyped-def]
    write_env(SCHEDULER_ENV)
    create_campaigns_table()
    monkeypatch.setattr(scheduler_service, "utc_clock", lambda: FIXED_NOW)
    fake = FakeLambda()
    monkeypatch.setattr(AwsClients, "lambda_", property(lambda self: fake))
    monkeypatch.setattr(AwsClients, "lambda_invoke_client", lambda self, timeout: fake)
    return fake


def _invoke(*args: str, user_input: str | None = None) -> Any:
    return runner.invoke(app, list(args), input=user_input)


def _json(*args: str) -> tuple[int, Any, str]:
    result = _invoke("--output", "json", "scheduler", *args)
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result.exit_code, data, result.stderr


def test_run_yes_ok_json(fake_lambda: FakeLambda) -> None:
    put_campaigns([campaign_item("n-1", PARTITION), campaign_item("n-2", PARTITION, user="57300")])

    code, data, _ = _json("run", "--yes")

    assert code == 0
    assert data["partition"] == PARTITION
    assert data["preview"]["por_app_id"] == {"others-test": 2}
    assert data["invocation"]["status_code"] == 200
    assert data["invocation"]["request_id"] == "req-1"
    assert data["invocation"]["payload"]["detail"]["total"] == 2
    assert data["outcome"] == "OK"
    assert fake_lambda.payloads == [{}]


def test_preview_warns_other_apps_and_no_cancels(fake_lambda: FakeLambda) -> None:
    put_campaigns(
        [campaign_item("n-1", PARTITION), campaign_item("n-2", PARTITION, app_id="otra-app")]
    )

    result = _invoke("scheduler", "run", user_input="n\n")

    assert result.exit_code == 0
    assert "otra-app" in result.stderr
    assert "otros equipos" in result.stderr
    assert "cancelada" in result.stderr
    assert fake_lambda.calls == []


def test_empty_partition_warns_and_still_asks(fake_lambda: FakeLambda) -> None:
    result = _invoke("scheduler", "run", user_input="y\n")

    assert result.exit_code == 0
    assert "no enviará nada" in result.stderr
    assert "0 notificación(es)" in result.stdout  # el prompt de typer.confirm
    assert len(fake_lambda.calls) == 1


def test_run_twice_invokes_twice(fake_lambda: FakeLambda) -> None:
    assert _invoke("scheduler", "run", "--yes").exit_code == 0
    assert _invoke("scheduler", "run", "--yes").exit_code == 0

    assert len(fake_lambda.calls) == 2


def test_tail_shows_log(fake_lambda: FakeLambda) -> None:
    result = _invoke("scheduler", "run", "--yes", "--tail")

    assert result.exit_code == 0
    assert fake_lambda.calls[0]["LogType"] == "Tail"


def test_function_error_exits_1(fake_lambda: FakeLambda) -> None:
    fake_lambda.queue = [({"errorMessage": "boom", "errorType": "RuntimeError"}, "Unhandled")]

    result = _invoke("scheduler", "run", "--yes")

    assert result.exit_code == 1
    assert "Unhandled" in result.stderr
    assert "boom" in result.stderr


def test_failed_notifications_exit_1(fake_lambda: FakeLambda) -> None:
    fake_lambda.queue = [scheduler_payload(total=3, failed=1)]

    code, data, stderr = _json("run", "--yes")

    assert code == 1
    assert data["outcome"] == "FALLA"
    assert "1 notificación(es) fallidas" in stderr


def test_read_timeout_is_unknown_exit_3(fake_lambda: FakeLambda) -> None:
    import boto3

    boto3.client("logs", region_name="us-east-1").create_log_group(logGroupName=SCHEDULER_LOG_GROUP)
    fake_lambda.queue = [ReadTimeoutError(endpoint_url="https://lambda")]

    code, data, stderr = _json("run", "--yes")

    assert code == 3
    assert data["outcome"] == "DESCONOCIDO"
    assert data["invocation"]["status_code"] is None
    assert len(fake_lambda.calls) == 1
    assert "DESCONOCIDO" in stderr


def test_throttling_then_success_exit_0(fake_lambda: FakeLambda, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("campaigns_cli.services.lambda_service.time.sleep", lambda _: None)
    fake_lambda.queue = [client_error("TooManyRequestsException", 429), scheduler_payload()]

    result = _invoke("scheduler", "run", "--yes")

    assert result.exit_code == 0
    assert len(fake_lambda.calls) == 2


def test_access_denied_exit_3(fake_lambda: FakeLambda) -> None:
    fake_lambda.queue = [client_error("AccessDeniedException", 403)]

    result = _invoke("scheduler", "run", "--yes")

    assert result.exit_code == 3
    assert "solo lectura no pueden invocar" in result.stderr


def test_health_sends_health_event_without_confirmation(fake_lambda: FakeLambda) -> None:
    fake_lambda.queue = [{"statusCode": 200, "message": "Kafka OK"}]

    code, data, _ = _json("health")

    assert code == 0
    assert data["kafka_ok"] is True
    assert fake_lambda.payloads == [{"type": "health"}]


def test_health_kafka_down_exit_1(fake_lambda: FakeLambda) -> None:
    fake_lambda.queue = [{"statusCode": 500, "message": "Kafka no responde"}]

    result = _invoke("scheduler", "health")

    assert result.exit_code == 1


@pytest.mark.parametrize("command", ["run", "health"])
def test_blocked_in_prod(write_env, fake_lambda: FakeLambda, command: str) -> None:  # type: ignore[no-untyped-def]
    write_env(SCHEDULER_ENV + "CAMPAIGNS_ENV=prod\n")

    result = _invoke("scheduler", command, "--yes" if command == "run" else "--tail")

    assert result.exit_code == 2
    assert "prod" in result.stderr
    assert fake_lambda.calls == []


def test_missing_settings_exit_2(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("AWS_REGION=us-east-1\n")

    result = _invoke("scheduler", "run", "--yes")

    assert result.exit_code == 2
    assert "SCHEDULER_LAMBDA_NAME" in result.stderr
    assert "CAMPAIGNS_TABLE_NAME" in result.stderr
