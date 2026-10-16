"""Cliente Lambda falso para scheduler_Lambda: moto necesita Docker para ejecutar Lambdas."""

import io
import json
from typing import Any

from botocore.exceptions import ClientError
from botocore.response import StreamingBody

SCHEDULER = "scheduler-dev"
SCHEDULER_LOG_GROUP = f"/aws/lambda/{SCHEDULER}"


def scheduler_payload(total: int = 2, failed: int = 0) -> dict[str, Any]:
    """Respuesta de `app.py:handler` del scheduler."""
    return {
        "statusCode": 200,
        "message": "Execution completed",
        "execution_datetime": "2026-10-14 22:00:00",
        "detail": {"successful": total - failed, "failed": failed, "total": total},
    }


def client_error(code: str, status: int, operation: str = "Invoke") -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": f"{code} simulado"},
            "ResponseMetadata": {"HTTPStatusCode": status, "RequestId": "req-err"},
        },
        operation,
    )


class FakeLambda:
    """Responde `get_function_configuration` y una cola de respuestas o excepciones a `invoke`."""

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = timeout
        self.queue: list[Any] = []
        self.calls: list[dict[str, Any]] = []
        self.read_timeouts: list[int] = []

    def factory(self, read_timeout: int) -> "FakeLambda":
        self.read_timeouts.append(read_timeout)
        return self

    def get_function_configuration(self, FunctionName: str) -> dict[str, Any]:  # noqa: N803
        return {"FunctionName": FunctionName, "Timeout": self.timeout}

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        item = self.queue.pop(0) if self.queue else scheduler_payload()
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            payload, function_error = item
        else:
            payload, function_error = item, None
        raw = json.dumps(payload).encode()
        response: dict[str, Any] = {
            "StatusCode": 200,
            "ExecutedVersion": "$LATEST",
            "Payload": StreamingBody(io.BytesIO(raw), len(raw)),
            "ResponseMetadata": {"RequestId": f"req-{len(self.calls)}"},
        }
        if function_error:
            response["FunctionError"] = function_error
        return response

    @property
    def payloads(self) -> list[Any]:
        return [json.loads(call["Payload"]) for call in self.calls]
