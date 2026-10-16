"""Invocación de Lambdas: una invocación pedida por el usuario = una ejecución (ADR-0010).

- Solo `RequestResponse`: Lambda no reintenta las invocaciones síncronas (sí las `Event`).
- El cliente de `Invoke` no reintenta (`total_max_attempts == 1`) y espera la respuesta
  `Timeout + 30` segundos: un `ReadTimeoutError` reenviado por el SDK ejecutaría la función otra
  vez mientras la primera sigue corriendo.
- La CLI reintenta (máx. 3, espera 1-2-4 s) solo los errores en los que AWS garantiza que la
  función no corrió (`RETRYABLE`).
- Los errores ambiguos (`AMBIGUOUS`: la función pudo haber corrido) no se reintentan: el
  resultado queda `DESCONOCIDO`.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    HTTPClientError,
)

from campaigns_cli.errors import AwsError, client_error_code, is_access_denied
from campaigns_cli.timeutils import colombia_now

if TYPE_CHECKING:
    from mypy_boto3_lambda import LambdaClient

# Margen sobre el `Timeout` de la función para el `read_timeout` del cliente de invocación.
READ_TIMEOUT_MARGIN = 30
# Reintentos de la CLI para errores en los que la función no corrió.
RETRY_DELAYS = (1.0, 2.0, 4.0)

# AWS rechazó la petición antes de ejecutar la función (throttling) o no se llegó a enviar.
RETRYABLE_CODES = frozenset({"TooManyRequestsException"})
RETRYABLE_EXCEPTIONS = (EndpointConnectionError, ConnectTimeoutError)
# La petición se envió y no hubo respuesta clara: la función pudo haber corrido.
AMBIGUOUS_CODES = frozenset({"ServiceException"})
AMBIGUOUS_EXCEPTIONS = (HTTPClientError,)  # ReadTimeoutError, ConnectionClosedError

InvokeClientFactory = Callable[[int], "LambdaClient"]


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    return isinstance(exc, ClientError) and client_error_code(exc) in RETRYABLE_CODES


def is_ambiguous(exc: Exception) -> bool:
    if isinstance(exc, AMBIGUOUS_EXCEPTIONS):
        return True
    if isinstance(exc, ClientError):
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return client_error_code(exc) in AMBIGUOUS_CODES or status >= 500
    return False


@dataclass
class InvokeResult:
    """Resultado de una invocación. Sin `status_code`, el resultado es desconocido."""

    function: str
    started_at: datetime  # hora Colombia, antes del primer intento
    attempts: int
    status_code: int | None = None
    function_error: str | None = None
    executed_version: str | None = None
    request_id: str | None = None
    payload: Any = None
    log_tail: str | None = None
    error: str | None = None

    @property
    def unknown(self) -> bool:
        return self.status_code is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "function_error": self.function_error,
            "executed_version": self.executed_version,
            "request_id": self.request_id,
            "attempts": self.attempts,
            "error": self.error,
            "payload": self.payload,
        }


def decode_payload(raw: bytes) -> Any:
    """JSON de la respuesta; si no lo es, el texto tal cual."""
    text = raw.decode("utf-8", errors="replace")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _request_id(response: Mapping[str, Any]) -> str | None:
    value = response.get("ResponseMetadata", {}).get("RequestId")
    return str(value) if value else None


class LambdaService:
    def __init__(
        self,
        client: LambdaClient,
        invoke_client: InvokeClientFactory,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = colombia_now,
    ) -> None:
        """`client` lee la configuración; `invoke_client(read_timeout)` crea el cliente sin
        reintentos que invoca."""
        self.client = client
        self.invoke_client = invoke_client
        self.sleep = sleep
        self.clock = clock

    def function_timeout(self, name: str) -> int:
        """`Timeout` de la función en segundos."""
        return int(self.client.get_function_configuration(FunctionName=name)["Timeout"])

    def invoke_once(self, name: str, payload: Mapping[str, Any], *, tail: bool) -> InvokeResult:
        """Invoca la función de forma síncrona y produce como máximo una ejecución.

        Lanza `AwsError` con `AccessDeniedException` y deja pasar los demás errores no
        reintentables en los que la función no corrió (se traducen en `errors.translate`).
        """
        client = self.invoke_client(self.function_timeout(name) + READ_TIMEOUT_MARGIN)
        body = json.dumps(payload).encode("utf-8")
        result = InvokeResult(function=name, started_at=self.clock(), attempts=0)
        for delay in (*RETRY_DELAYS, None):
            result.attempts += 1
            try:
                response = client.invoke(
                    FunctionName=name,
                    InvocationType="RequestResponse",
                    LogType="Tail" if tail else "None",
                    Payload=body,
                )
            except Exception as exc:
                if is_ambiguous(exc):
                    result.error = _describe(exc)
                    if isinstance(exc, ClientError):
                        result.request_id = _request_id(exc.response)
                    return result
                if isinstance(exc, ClientError) and is_access_denied(exc):
                    raise AwsError(
                        f"Permiso denegado en `Invoke` de {name}: las credenciales de solo "
                        "lectura no pueden invocar la Lambda (falta lambda:InvokeFunction)."
                    ) from exc
                if delay is None or not is_retryable(exc):
                    raise
                self.sleep(delay)
                continue
            result.status_code = int(response["StatusCode"])
            result.function_error = response.get("FunctionError")
            result.executed_version = response.get("ExecutedVersion")
            result.request_id = _request_id(response)
            result.payload = decode_payload(response["Payload"].read())
            log_result = response.get("LogResult")
            if log_result:
                result.log_tail = base64.b64decode(log_result).decode("utf-8", errors="replace")
            return result
        raise AssertionError("inalcanzable")  # pragma: no cover


def _describe(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        message = exc.response.get("Error", {}).get("Message", "")
        return f"{client_error_code(exc)}: {message}".rstrip(": ")
    return f"{type(exc).__name__}: {exc}"
