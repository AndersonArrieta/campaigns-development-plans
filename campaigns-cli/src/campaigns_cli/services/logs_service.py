"""Consultas a CloudWatch Logs: búsqueda con Logs Insights, eventos recientes y log groups.

Las horas que recibe y devuelve este módulo son de Colombia, sin zona; CloudWatch trabaja en
epoch (ms) y Logs Insights devuelve `@timestamp` en UTC.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.timeutils import (
    COLOMBIA_TZ,
    colombia_to_epoch_ms,
    epoch_ms_to_colombia,
)

if TYPE_CHECKING:
    from mypy_boto3_logs import CloudWatchLogsClient

MIN_TERM_LENGTH = 6
# Logs Insights acepta hasta 50 log groups por consulta.
MAX_GROUPS_PER_QUERY = 50
FINAL_STATUSES = frozenset({"Complete", "Failed", "Cancelled", "Timeout", "Unknown"})


@dataclass(frozen=True)
class LogHit:
    timestamp: datetime
    group: str
    stream: str
    message: str
    event_id: str = ""

    @property
    def component(self) -> str:
        return component_name(self.group)

    def as_dict(self) -> dict[str, Any]:
        return {
            "hora": self.timestamp.isoformat(sep=" ", timespec="milliseconds"),
            "componente": self.component,
            "log_group": self.group,
            "log_stream": self.stream,
            "mensaje": self.message,
        }


@dataclass
class SearchResult:
    hits: list[LogHit]
    counts: dict[str, int]
    status: str = "Complete"

    def summary(self) -> list[dict[str, Any]]:
        return [
            {"componente": component_name(group), "log_group": group, "coincidencias": count}
            for group, count in self.counts.items()
        ]


def component_name(group: str) -> str:
    """Nombre corto del log group para mostrar.

    `/aws/lambda/nu0284001-artemis-plc-dev-campaigns-ingester-lambda` → `campaigns-ingester-lambda`.
    """
    name = group.rstrip("/").rsplit("/", 1)[-1]
    marker = "-campaigns-"
    if name.startswith("nu0284001-") and marker in name:
        return "campaigns-" + name.split(marker, 1)[1]
    return name


def build_query(term: str, limit: int) -> str:
    # `like "texto"` busca la subcadena literal, sin interpretar regex.
    literal = term.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "fields @timestamp, @log, @logStream, @message\n"
        f'| filter @message like "{literal}"\n'
        "| sort @timestamp asc\n"
        f"| limit {limit}"
    )


def _insights_timestamp(value: str) -> datetime:
    """`2026-10-13 15:04:05.123` (UTC) → hora Colombia."""
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=UTC)
    return parsed.astimezone(COLOMBIA_TZ).replace(tzinfo=None)


def _group_from_log_field(value: str, groups: Sequence[str]) -> str:
    """`@log` llega como `<cuenta>:<log group>`."""
    name = value.split(":", 1)[1] if ":" in value else value
    return next((group for group in groups if group == name), name)


def _clean(message: str) -> str:
    return message.rstrip("\n")


class LogsService:
    def __init__(
        self,
        client: CloudWatchLogsClient,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.sleep = sleep
        self.clock = clock

    def list_groups(self, prefix: str) -> list[dict[str, Any]]:
        paginator = self.client.get_paginator("describe_log_groups")
        groups = []
        for page in paginator.paginate(logGroupNamePrefix=prefix):
            for group in page.get("logGroups", []):
                created = group.get("creationTime")
                groups.append(
                    {
                        "log_group": group["logGroupName"],
                        "retencion_dias": group.get("retentionInDays"),
                        "tamano_mb": round(group.get("storedBytes", 0) / 1_048_576, 2),
                        "creado": epoch_ms_to_colombia(created).date() if created else None,
                    }
                )
        return groups

    def search(
        self,
        groups: Sequence[str],
        term: str,
        start: datetime,
        end: datetime,
        *,
        limit: int,
        timeout: float,
        poll_interval: float,
    ) -> SearchResult:
        """Busca `term` en los log groups con Logs Insights (lotes de 50 grupos)."""
        if len(term.strip()) < MIN_TERM_LENGTH:
            raise UsageError(
                f"El texto a buscar debe tener al menos {MIN_TERM_LENGTH} caracteres "
                "(evita consultas costosas)."
            )
        if not groups:
            raise UsageError("No hay log groups para buscar.")

        counts = dict.fromkeys(groups, 0)
        hits: list[LogHit] = []
        for index in range(0, len(groups), MAX_GROUPS_PER_QUERY):
            batch = list(groups[index : index + MAX_GROUPS_PER_QUERY])
            rows = self._run_query(batch, term.strip(), start, end, limit, timeout, poll_interval)
            for row in rows:
                fields = {field["field"]: field["value"] for field in row if "field" in field}
                group = _group_from_log_field(fields.get("@log", ""), batch)
                hit = LogHit(
                    timestamp=_insights_timestamp(fields["@timestamp"]),
                    group=group,
                    stream=fields.get("@logStream", ""),
                    message=_clean(fields.get("@message", "")),
                )
                hits.append(hit)
                counts[group] = counts.get(group, 0) + 1

        hits.sort(key=lambda hit: hit.timestamp)
        return SearchResult(hits[:limit], counts)

    def _run_query(
        self,
        groups: list[str],
        term: str,
        start: datetime,
        end: datetime,
        limit: int,
        timeout: float,
        poll_interval: float,
    ) -> list[Any]:
        query_id = self.client.start_query(
            logGroupNames=groups,
            startTime=colombia_to_epoch_ms(start) // 1000,
            endTime=colombia_to_epoch_ms(end) // 1000,
            queryString=build_query(term, limit),
            limit=limit,
        )["queryId"]
        deadline = self.clock() + timeout
        while True:
            response = self.client.get_query_results(queryId=query_id)
            status = response["status"]
            if status == "Complete":
                return list(response.get("results", []))
            if status in FINAL_STATUSES:
                raise TestFailedError(f"La consulta de Logs Insights terminó con estado {status}.")
            if self.clock() >= deadline:
                self.client.stop_query(queryId=query_id)
                raise TestFailedError(
                    f"La consulta no terminó en {timeout:.0f}s; se canceló. "
                    "Reduce el rango de tiempo o sube CLI_WAIT_TIMEOUT_SECONDS."
                )
            self.sleep(poll_interval)

    def events(
        self,
        group: str,
        start: datetime,
        end: datetime | None = None,
        *,
        pattern: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[LogHit], bool]:
        """Eventos de un log group en orden cronológico. Devuelve (eventos, truncado)."""
        kwargs: dict[str, Any] = {
            "logGroupName": group,
            "startTime": colombia_to_epoch_ms(start),
        }
        if end is not None:
            kwargs["endTime"] = colombia_to_epoch_ms(end)
        if pattern:
            # Entre comillas: CloudWatch busca el texto literal.
            kwargs["filterPattern"] = '"' + pattern.replace('"', '\\"') + '"'

        hits: list[LogHit] = []
        paginator = self.client.get_paginator("filter_log_events")
        for page in paginator.paginate(**kwargs):
            for event in page.get("events", []):
                hits.append(
                    LogHit(
                        timestamp=epoch_ms_to_colombia(event["timestamp"]),
                        group=group,
                        stream=event.get("logStreamName", ""),
                        message=_clean(event.get("message", "")),
                        event_id=event.get("eventId", ""),
                    )
                )
        hits.sort(key=lambda hit: hit.timestamp)
        if limit is not None and len(hits) > limit:
            # Se conservan los más recientes, como `tail`.
            return hits[-limit:], True
        return hits, False

    def follow(
        self,
        group: str,
        start: datetime,
        *,
        pattern: str | None = None,
        interval: float,
        max_polls: int | None = None,
    ) -> Iterator[LogHit]:
        """Consulta periódicamente y entrega solo los eventos nuevos (Ctrl+C para salir)."""
        seen: set[str] = set()
        since = start
        polls = 0
        while max_polls is None or polls < max_polls:
            if polls:
                self.sleep(interval)
            polls += 1
            hits, _ = self.events(group, since, pattern=pattern)
            for hit in hits:
                key = hit.event_id or f"{hit.timestamp.isoformat()}|{hit.stream}|{hit.message}"
                if key in seen:
                    continue
                seen.add(key)
                yield hit
            if hits:
                # Se repite el último milisegundo: `seen` evita duplicados.
                since = max(since, hits[-1].timestamp)
