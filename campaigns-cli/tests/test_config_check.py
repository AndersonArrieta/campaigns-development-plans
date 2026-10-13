import json
from typing import Any

import boto3
import httpx
import pytest
from botocore.exceptions import ClientError
from typer.testing import CliRunner

from campaigns_cli.aws import AwsClients
from campaigns_cli.http import HttpClients
from campaigns_cli.main import app
from campaigns_cli.state import AppState
from tests.channel_fixtures import BASE_URL, CHANNEL_ENV, CLIENT_SECRET, TOKEN_URL, FakeServer

# Terminal ancha para que rich no parta los nombres de recursos en varias líneas.
runner = CliRunner(env={"COLUMNS": "200"})

REGION = "us-east-1"
BUCKET = "campaigns-input-dev"
TABLE = "campaigns-dev"
LOGS_TABLE = "campaigns-logs-dev"
INDEX = "campaign_id-index"
INGESTER = "ingester-dev"
SCHEDULER = "scheduler-dev"
LOG_GROUPS = ("/aws/lambda/ingester-dev", "/aws/lambda/scheduler-dev")

ENV = f"""
AWS_REGION={REGION}
CAMPAIGNS_INPUT_BUCKET={BUCKET}
CAMPAIGNS_TABLE_NAME={TABLE}
CAMPAIGNS_TABLE_CAMPAIGN_INDEX={INDEX}
CAMPAIGNS_LOGS_TABLE_NAME={LOGS_TABLE}
INGESTER_LAMBDA_NAME={INGESTER}
SCHEDULER_LAMBDA_NAME={SCHEDULER}
CAMPAIGNS_LOG_GROUPS={",".join(LOG_GROUPS)}
"""


def _create_table(with_index: bool = True) -> None:
    attributes = [
        {"AttributeName": "datetime", "AttributeType": "S"},
        {"AttributeName": "notification_id", "AttributeType": "S"},
    ]
    kwargs: dict[str, Any] = {}
    if with_index:
        attributes.append({"AttributeName": "campaign_id", "AttributeType": "S"})
        kwargs["GlobalSecondaryIndexes"] = [
            {
                "IndexName": INDEX,
                "KeySchema": [{"AttributeName": "campaign_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ]
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName=TABLE,
        KeySchema=[
            {"AttributeName": "datetime", "KeyType": "HASH"},
            {"AttributeName": "notification_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=attributes,
        BillingMode="PAY_PER_REQUEST",
        **kwargs,
    )


class FakeLambda:
    """Cliente Lambda mínimo. Crear Lambdas en moto exige simular IAM (~7 s por prueba)."""

    def __init__(self) -> None:
        self.functions: set[str] = set()

    def get_function(self, FunctionName: str) -> dict[str, Any]:  # noqa: N803
        if FunctionName not in self.functions:
            raise ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": FunctionName}},
                "GetFunction",
            )
        return {"Configuration": {"FunctionName": FunctionName}}


@pytest.fixture
def fake_lambda(monkeypatch: pytest.MonkeyPatch) -> FakeLambda:
    fake = FakeLambda()
    monkeypatch.setattr(AwsClients, "lambda_", property(lambda self: fake))
    return fake


@pytest.fixture
def fake_channel(monkeypatch: pytest.MonkeyPatch) -> FakeServer:
    server = FakeServer()

    def http(self: AppState) -> HttpClients:
        if self._http is None:
            self._http = HttpClients(self.settings, transport=server.transport())
        return self._http

    monkeypatch.setattr(AppState, "http", property(http))
    return server


def _create_logs_table() -> None:
    boto3.client("dynamodb", region_name=REGION).create_table(
        TableName=LOGS_TABLE,
        KeySchema=[
            {"AttributeName": "app_id", "KeyType": "HASH"},
            {"AttributeName": "datetime", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "app_id", "AttributeType": "S"},
            {"AttributeName": "datetime", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_all(
    fake_lambda: FakeLambda, *, table_index: bool = True, skip: tuple[str, ...] = ()
) -> None:
    if "bucket" not in skip:
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
    if "table" not in skip:
        _create_table(with_index=table_index)
    if "logs" not in skip:
        _create_logs_table()
    for name in (INGESTER, SCHEDULER):
        if name not in skip:
            fake_lambda.functions.add(name)
    logs = boto3.client("logs", region_name=REGION)
    for group in LOG_GROUPS:
        if group not in skip:
            logs.create_log_group(logGroupName=group)


def _check() -> tuple[int, dict[str, Any], str]:
    result = runner.invoke(app, ["--output", "json", "config", "check"])
    report = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.exit_code, report, result.stderr


def _statuses(report: dict[str, Any]) -> dict[str, str]:
    return {f"{r['recurso']}:{r['nombre']}": r["estado"] for r in report["recursos"]}


@pytest.mark.usefixtures("mocked_aws")
def test_all_resources_ok(write_env, fake_lambda: FakeLambda, fake_channel: FakeServer) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + CHANNEL_ENV)
    _create_all(fake_lambda)

    exit_code, report, _ = _check()

    assert exit_code == 0
    assert report["ok"] is True
    assert report["identidad"]["cuenta"]
    assert set(_statuses(report).values()) == {"OK"}
    assert _statuses(report)[f"Cognito:{TOKEN_URL}/oauth2/token"] == "OK"
    assert _statuses(report)[f"Fake channel:{BASE_URL}"] == "OK"
    assert fake_channel.message_requests[0].url.path.endswith("/whatsapp/get-messages/0000000000")


@pytest.mark.usefixtures("mocked_aws")
def test_channel_is_optional(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    _create_all(fake_lambda)

    exit_code, report, _ = _check()

    assert exit_code == 0
    assert _statuses(report)["Cognito:"] == "OPCIONAL"
    assert _statuses(report)["Fake channel:"] == "OPCIONAL"


@pytest.mark.usefixtures("mocked_aws")
def test_channel_partially_configured(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + CHANNEL_ENV.replace(f"COGNITO_CLIENT_SECRET={CLIENT_SECRET}", ""))
    _create_all(fake_lambda)

    exit_code, report, _ = _check()

    cognito = next(r for r in report["recursos"] if r["recurso"] == "Cognito")
    assert exit_code == 1
    assert cognito["estado"] == "FALTA CONFIG"
    assert "COGNITO_CLIENT_SECRET" in cognito["detalle"]


@pytest.mark.usefixtures("mocked_aws")
def test_channel_rejected_credentials(  # type: ignore[no-untyped-def]
    write_env, fake_lambda: FakeLambda, fake_channel: FakeServer
) -> None:
    write_env(ENV + CHANNEL_ENV)
    _create_all(fake_lambda)
    fake_channel.token_status = 401

    exit_code, report, _ = _check()

    assert exit_code == 1
    assert _statuses(report)[f"Cognito:{TOKEN_URL}/oauth2/token"] == "SIN PERMISO"
    assert _statuses(report)[f"Fake channel:{BASE_URL}"] == "ERROR"
    assert fake_channel.message_requests == []


@pytest.mark.usefixtures("mocked_aws")
def test_fake_channel_wrong_url(  # type: ignore[no-untyped-def]
    write_env, fake_lambda: FakeLambda, fake_channel: FakeServer
) -> None:
    write_env(ENV + CHANNEL_ENV)
    _create_all(fake_lambda)
    fake_channel.inbox = [httpx.Response(404, text="Not Found")]

    exit_code, report, _ = _check()

    fake = next(r for r in report["recursos"] if r["recurso"] == "Fake channel")
    assert exit_code == 1
    assert fake["estado"] == "ERROR"
    assert "FAKE_CHANNEL_BASE_URL" in fake["detalle"]


@pytest.mark.usefixtures("mocked_aws")
def test_table_output(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    _create_all(fake_lambda)

    result = runner.invoke(app, ["config", "check"])

    assert result.exit_code == 0
    assert "Identidad AWS" in result.stdout
    assert BUCKET in result.stdout


@pytest.mark.usefixtures("mocked_aws")
def test_missing_bucket(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    _create_all(fake_lambda, skip=("bucket",))

    exit_code, report, stderr = _check()

    assert exit_code == 1
    assert report["ok"] is False
    assert _statuses(report)[f"S3 bucket:{BUCKET}"] == "NO EXISTE"
    assert "1 recurso(s) con problemas" in stderr


@pytest.mark.usefixtures("mocked_aws")
def test_missing_table_lambda_and_log_group(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    _create_all(fake_lambda, skip=("table", "logs", SCHEDULER, LOG_GROUPS[1]))

    exit_code, report, _ = _check()

    statuses = _statuses(report)
    assert exit_code == 1
    assert statuses[f"DynamoDB tabla:{TABLE}"] == "NO EXISTE"
    assert statuses[f"DynamoDB logs:{LOGS_TABLE}"] == "NO EXISTE"
    assert statuses[f"DynamoDB GSI:{INDEX}"] == "ERROR"
    assert statuses[f"Lambda:{SCHEDULER}"] == "NO EXISTE"
    assert statuses[f"Lambda:{INGESTER}"] == "OK"
    assert statuses[f"Log group:{LOG_GROUPS[1]}"] == "NO EXISTE"
    assert statuses[f"Log group:{LOG_GROUPS[0]}"] == "OK"


@pytest.mark.usefixtures("mocked_aws")
def test_configured_index_not_in_table(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)
    _create_all(fake_lambda, table_index=False)

    exit_code, report, _ = _check()

    assert exit_code == 1
    assert _statuses(report)[f"DynamoDB GSI:{INDEX}"] == "NO EXISTE"


@pytest.mark.usefixtures("mocked_aws")
def test_index_is_optional(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV.replace(f"CAMPAIGNS_TABLE_CAMPAIGN_INDEX={INDEX}", ""))
    _create_all(fake_lambda, table_index=False)

    exit_code, report, _ = _check()

    assert exit_code == 0
    assert _statuses(report)["DynamoDB GSI:"] == "OPCIONAL"


@pytest.mark.usefixtures("mocked_aws")
def test_missing_variables(write_env, fake_lambda: FakeLambda) -> None:  # type: ignore[no-untyped-def]
    write_env(f"CAMPAIGNS_INPUT_BUCKET={BUCKET}\n")
    boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)

    exit_code, report, _ = _check()

    assert exit_code == 1
    missing = {r["variable"] for r in report["recursos"] if r["estado"] == "FALTA CONFIG"}
    assert missing == {
        "CAMPAIGNS_TABLE_NAME",
        "CAMPAIGNS_LOGS_TABLE_NAME",
        "INGESTER_LAMBDA_NAME",
        "SCHEDULER_LAMBDA_NAME",
        "CAMPAIGNS_LOG_GROUPS",
    }


def test_without_credentials_exits_3(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)

    result = runner.invoke(app, ["config", "check"])

    assert result.exit_code == 3
    assert "AWS_SECRET_ACCESS_KEY" in result.stderr
    assert "Traceback" not in result.stderr


def test_without_credentials_verbose_shows_traceback(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV)

    result = runner.invoke(app, ["--verbose", "config", "check"])

    assert result.exit_code == 3
    assert "Traceback" in result.stderr


def test_unknown_profile_exits_3(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "AWS_PROFILE=perfil-inexistente\n")

    result = runner.invoke(app, ["config", "check"])

    assert result.exit_code == 3
    assert "perfil-inexistente" in result.stderr


@pytest.mark.usefixtures("mocked_aws")
def test_uses_credentials_from_env_file(  # type: ignore[no-untyped-def]
    write_env, fake_lambda: FakeLambda, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_all(fake_lambda)
    # Sin credenciales en el proceso: solo quedan las del .env.
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name)
    write_env(ENV + "AWS_ACCESS_KEY_ID=AKIAFROMENVFILE\nAWS_SECRET_ACCESS_KEY=secreto\n")

    exit_code, report, _ = _check()

    assert exit_code == 0
    assert report["ok"] is True
