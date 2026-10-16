"""Disparo a demanda de scheduler_Lambda (confirmado en su código):

- `app.py:handler` ignora el evento salvo `{"type": "health"}`, que solo prueba Kafka.
- Procesa solo la hora en curso en Colombia (`YYYY-MM-DD HH:00:00`, UTC-5): no se puede pedir
  otra partición.
- No es idempotente: cada ejecución vuelve a publicar en Kafka todas las notificaciones de la
  partición, de todos los `app_id`.
- Responde `{"statusCode", "message", "execution_datetime", "detail": {"successful", "failed",
  "total"}}` y deja `Execution result: {...}` en su log.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from campaigns_cli.services.dynamo_service import CampaignsTable
from campaigns_cli.services.lambda_service import InvokeResult, LambdaService
from campaigns_cli.services.logs_service import LogHit, LogsService
from campaigns_cli.timeutils import COLOMBIA_TZ, hour_floor, parse_datetime, to_dynamo

DISPATCH_PAYLOAD: dict[str, Any] = {}
HEALTH_PAYLOAD: dict[str, Any] = {"type": "health"}
EXECUTION_RESULT_MARKER = "Execution result"


def utc_clock() -> datetime:
    return datetime.now(UTC)


def current_partition(now: datetime | None = None) -> str:
    """Partición que procesaría el scheduler ahora: la hora en punto de Colombia."""
    moment = now if now is not None else utc_clock()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return to_dynamo(hour_floor(moment.astimezone(COLOMBIA_TZ).replace(tzinfo=None)))


class Outcome(StrEnum):
    OK = "OK"
    FALLA = "FALLA"
    DESCONOCIDO = "DESCONOCIDO"


@dataclass
class Preview:
    partition: str
    by_app: dict[str, int]
    test_app_id: str

    @property
    def total(self) -> int:
        return sum(self.by_app.values())

    @property
    def other_apps(self) -> list[str]:
        return [app_id for app_id in self.by_app if app_id != self.test_app_id]

    def rows(self) -> list[dict[str, Any]]:
        return [{"app_id": app_id, "filas": count} for app_id, count in self.by_app.items()]

    def as_dict(self) -> dict[str, Any]:
        return {"total": self.total, "por_app_id": self.by_app, "otras_apps": self.other_apps}


def detail_of(payload: Any) -> dict[str, Any]:
    """`detail` de la respuesta del scheduler (vacío si no viene)."""
    if isinstance(payload, dict) and isinstance(payload.get("detail"), dict):
        return dict(payload["detail"])
    return {}


def _count(value: Any) -> int:
    return int(value) if isinstance(value, int | float) else 0


def outcome_of(invocation: InvokeResult) -> Outcome:
    if invocation.unknown:
        return Outcome.DESCONOCIDO
    if invocation.function_error or _count(detail_of(invocation.payload).get("failed")) > 0:
        return Outcome.FALLA
    return Outcome.OK


def health_ok(invocation: InvokeResult) -> bool:
    """Kafka responde si la función no falló y su `statusCode` (si lo trae) es 200."""
    if invocation.unknown or invocation.function_error:
        return False
    payload = invocation.payload
    if isinstance(payload, dict) and "statusCode" in payload:
        return _count(payload["statusCode"]) == 200
    return True


@dataclass
class RunResult:
    preview: Preview
    partition_at_invoke: str
    invocation: InvokeResult
    log_hits: list[LogHit] = field(default_factory=list)

    @property
    def outcome(self) -> Outcome:
        return outcome_of(self.invocation)

    @property
    def partition_changed(self) -> bool:
        return self.partition_at_invoke != self.preview.partition

    def as_dict(self) -> dict[str, Any]:
        return {
            "partition": self.preview.partition,
            "partition_at_invoke": self.partition_at_invoke,
            "preview": self.preview.as_dict(),
            "invocation": self.invocation.as_dict(),
            "detail": detail_of(self.invocation.payload),
            "outcome": self.outcome,
            "log_tail": self.invocation.log_tail,
            "execution_results": [hit.as_dict() for hit in self.log_hits],
        }


class SchedulerService:
    def __init__(
        self,
        lambdas: LambdaService,
        function_name: str,
        *,
        table: CampaignsTable | None = None,
        logs: LogsService | None = None,
        log_group: str | None = None,
        test_app_id: str = "others-test",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.lambdas = lambdas
        self.function_name = function_name
        self.table = table
        self.logs = logs
        self.log_group = log_group
        self.test_app_id = test_app_id
        self.clock = clock or utc_clock

    def current_partition(self) -> str:
        return current_partition(self.clock())

    def preview(self) -> Preview:
        """Filas de la partición actual por `app_id`: lo que el scheduler reenviará a Kafka."""
        if self.table is None:
            raise ValueError("preview requiere la tabla de campañas")
        partition = self.current_partition()
        hour = parse_datetime(partition)
        items = self.table.list_range(hour, hour).items
        counts = Counter(str(item.get("app_id", "")) for item in items)
        return Preview(partition, dict(sorted(counts.items())), self.test_app_id)

    def run(self, preview: Preview, *, tail: bool) -> RunResult:
        """Invoca una vez el despacho. Si el resultado es desconocido, busca su
        `Execution result` en el log group del scheduler."""
        partition = self.current_partition()
        invocation = self.lambdas.invoke_once(self.function_name, DISPATCH_PAYLOAD, tail=tail)
        result = RunResult(preview, partition, invocation)
        if invocation.unknown and self.logs is not None and self.log_group:
            hits, _ = self.logs.events(
                self.log_group, invocation.started_at, pattern=EXECUTION_RESULT_MARKER
            )
            result.log_hits = hits
        return result

    def health(self, *, tail: bool = False) -> InvokeResult:
        """Invoca con `{"type": "health"}`: solo prueba la conexión a Kafka, no despacha."""
        return self.lambdas.invoke_once(self.function_name, HEALTH_PAYLOAD, tail=tail)
