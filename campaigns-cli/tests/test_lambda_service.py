"""Invocación sin reintentos que re-ejecuten la función: Stubber sobre el cliente real de
`AwsClients.lambda_invoke_client` y, para los errores de red, un `before-send` que los lanza."""

import base64
import io
import json
from typing import Any

import boto3
import pytest
from botocore.exceptions import ConnectionClosedError, ReadTimeoutError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from campaigns_cli.aws import AwsClients
from campaigns_cli.errors import AwsError
from campaigns_cli.services.lambda_service import (
    READ_TIMEOUT_MARGIN,
    LambdaService,
    decode_payload,
)
from campaigns_cli.settings import Settings

REGION = "us-east-1"
FUNCTION = "scheduler-dev"
FUNCTION_TIMEOUT = 300

pytestmark = pytest.mark.usefixtures("aws_credentials")


def invoke_response(
    payload: Any, *, function_error: str | None = None, log: str | None = None
) -> dict[str, Any]:
    raw = json.dumps(payload).encode()
    response: dict[str, Any] = {
        "StatusCode": 200,
        "ExecutedVersion": "$LATEST",
        "Payload": StreamingBody(io.BytesIO(raw), len(raw)),
        "ResponseMetadata": {"RequestId": "req-1", "HTTPStatusCode": 200},
    }
    if function_error:
        response["FunctionError"] = function_error
    if log is not None:
        response["LogResult"] = base64.b64encode(log.encode()).decode()
    return response


class Harness:
    """Crea el cliente de invocación con la fábrica real y cuenta las llamadas a Invoke
    (`invoke_calls`) y los envíos HTTP (`http_sends`)."""

    def __init__(self, timeout: int = FUNCTION_TIMEOUT) -> None:
        self.config_client = boto3.client("lambda", region_name=REGION)
        self.config_stub = Stubber(self.config_client)
        self.config_stub.add_response(
            "get_function_configuration", {"Timeout": timeout}, {"FunctionName": FUNCTION}
        )
        self.config_stub.activate()
        self.clients = AwsClients(Settings(aws_region=REGION))
        self.responses: list[tuple[str, Any]] = []
        self.send_error: Exception | None = None
        self.read_timeouts: list[int] = []
        self.invoke_client: Any = None
        self.invoke_calls = 0
        self.http_sends = 0
        self.sleeps: list[float] = []

    def factory(self, read_timeout: int) -> Any:
        self.read_timeouts.append(read_timeout)
        client = self.clients.lambda_invoke_client(read_timeout)
        client.meta.events.register("before-parameter-build.lambda.Invoke", self._count_call)
        if self.send_error is not None:
            client.meta.events.register("before-send.lambda.Invoke", self._fail_send)
        else:
            stubber = Stubber(client)
            for kind, value in self.responses:
                if kind == "ok":
                    stubber.add_response("invoke", value)
                else:
                    code, status = value
                    stubber.add_client_error(
                        "invoke", service_error_code=code, http_status_code=status
                    )
            stubber.activate()
        self.invoke_client = client
        return client

    def _count_call(self, **_: Any) -> None:
        self.invoke_calls += 1

    def _fail_send(self, **_: Any) -> None:
        self.http_sends += 1
        assert self.send_error is not None
        raise self.send_error

    def service(self) -> LambdaService:
        return LambdaService(self.config_client, self.factory, sleep=self.sleeps.append)


def test_invoke_client_has_single_attempt_and_long_read_timeout() -> None:
    harness = Harness()
    harness.responses = [("ok", invoke_response({"statusCode": 200}))]

    harness.service().invoke_once(FUNCTION, {}, tail=False)

    config = harness.invoke_client.meta.config
    assert config.retries["total_max_attempts"] == 1
    assert config.read_timeout >= FUNCTION_TIMEOUT + 30
    assert harness.read_timeouts == [FUNCTION_TIMEOUT + READ_TIMEOUT_MARGIN]
    assert config.tcp_keepalive is True


def test_success_returns_payload_request_id_and_tail() -> None:
    harness = Harness()
    payload = {"statusCode": 200, "detail": {"successful": 2, "failed": 0, "total": 2}}
    harness.responses = [("ok", invoke_response(payload, log="START\nExecution result: {}\n"))]

    result = harness.service().invoke_once(FUNCTION, {}, tail=True)

    assert not result.unknown
    assert result.status_code == 200
    assert result.payload == payload
    assert result.request_id == "req-1"
    assert result.executed_version == "$LATEST"
    assert result.log_tail is not None and "Execution result" in result.log_tail
    assert result.attempts == 1


@pytest.mark.parametrize(
    "error",
    [
        ReadTimeoutError(endpoint_url="https://lambda.us-east-1.amazonaws.com"),
        ConnectionClosedError(endpoint_url="https://lambda.us-east-1.amazonaws.com"),
    ],
)
def test_ambiguous_network_error_is_not_retried(error: Exception) -> None:
    harness = Harness()
    harness.send_error = error

    result = harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert result.unknown
    assert harness.invoke_calls == 1
    assert harness.http_sends == 1  # el SDK no reenvió la petición
    assert result.error is not None and type(error).__name__ in result.error
    assert harness.sleeps == []


def test_service_exception_is_unknown_with_single_call() -> None:
    harness = Harness()
    harness.responses = [("error", ("ServiceException", 500))]

    result = harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert result.unknown
    assert harness.invoke_calls == 1
    assert result.error is not None and "ServiceException" in result.error


def test_throttling_is_retried_by_the_cli() -> None:
    harness = Harness()
    harness.responses = [
        ("error", ("TooManyRequestsException", 429)),
        ("ok", invoke_response({"statusCode": 200})),
    ]

    result = harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert result.status_code == 200
    assert harness.invoke_calls == 2
    assert result.attempts == 2
    assert harness.sleeps == [1.0]


def test_throttling_gives_up_after_three_retries() -> None:
    harness = Harness()
    harness.responses = [("error", ("TooManyRequestsException", 429))] * 4

    with pytest.raises(Exception, match="TooManyRequestsException"):
        harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert harness.invoke_calls == 4
    assert harness.sleeps == [1.0, 2.0, 4.0]


def test_access_denied_has_permissions_message() -> None:
    harness = Harness()
    harness.responses = [("error", ("AccessDeniedException", 403))]

    with pytest.raises(AwsError, match="solo lectura no pueden invocar"):
        harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert harness.invoke_calls == 1


def test_other_client_errors_are_raised_without_retry() -> None:
    harness = Harness()
    harness.responses = [("error", ("ResourceNotFoundException", 404))]

    with pytest.raises(Exception, match="ResourceNotFoundException"):
        harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert harness.invoke_calls == 1


def test_function_error_is_reported() -> None:
    harness = Harness()
    error = {"errorMessage": "boom", "errorType": "RuntimeError"}
    harness.responses = [("ok", invoke_response(error, function_error="Unhandled"))]

    result = harness.service().invoke_once(FUNCTION, {}, tail=False)

    assert result.function_error == "Unhandled"
    assert result.payload == error


def test_decode_payload_tolerates_text_and_empty() -> None:
    assert decode_payload(b"") is None
    assert decode_payload(b"no es json") == "no es json"
    assert decode_payload(b'{"a": 1}') == {"a": 1}
