"""Historial de cargas: une cada carga de la tabla de logs con las filas que dejó en la tabla de
campañas y reconoce las reprogramaciones de platform_campaigns_ms.

Reprogramaciones (confirmado en el código del ms, `NotificationDynamoDbAdapter.createItem`):
el ms escribe una fila **nueva** con el mismo `notification_id` y otra `datetime`, y nadie borra
la anterior. Dentro de un `notification_id`:
    - la fila de menor `datetime` es la original (el ms siempre mueve la fecha hacia adelante);
    - las demás son `FUERA_DE_HORARIO` si `retries` no cambió respecto de la fila anterior
      (`BatchMessageUseCase.reschedule`) y `REINTENTO` si subió (`RetryUseCase`).

El estado de cada fila se calcula con la hora Colombia actual: `PENDIENTE` (hora futura),
`EN_CURSO` (hora actual) o `PASADA`. `PASADA` no prueba que se haya enviado.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from campaigns_cli.services.dynamo_service import (
    CAMPAIGN_PK,
    CAMPAIGN_SK,
    CampaignsTable,
    Item,
    LogEntry,
    LogsTable,
    parse_log_entry,
)
from campaigns_cli.timeutils import hour_floor

FAILED_STATUS = "FAILED"


class RowType(StrEnum):
    ORIGINAL = "ORIGINAL"
    FUERA_DE_HORARIO = "FUERA_DE_HORARIO"
    REINTENTO = "REINTENTO"


class RowState(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_CURSO = "EN_CURSO"
    PASADA = "PASADA"


def parse_retries(value: Any) -> int:
    """`retries` se guarda como texto ("0"); se compara como entero."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def row_state(scheduled: str, now: datetime) -> RowState:
    """Estado de una fila según su hora programada (hora Colombia) y la hora actual."""
    try:
        when = hour_floor(datetime.strptime(scheduled[:19], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return RowState.PASADA
    current = hour_floor(now)
    if when > current:
        return RowState.PENDIENTE
    if when == current:
        return RowState.EN_CURSO
    return RowState.PASADA


@dataclass
class TimelineRow:
    item: Item
    tipo: RowType
    estado: RowState

    @property
    def datetime(self) -> str:
        return str(self.item.get(CAMPAIGN_PK, ""))

    @property
    def retries(self) -> int:
        return parse_retries(self.item.get("retries"))

    def summary(self) -> dict[str, Any]:
        return {
            "hora_colombia": self.datetime,
            "retries": self.retries,
            "tipo": self.tipo,
            "estado": self.estado,
        }

    def with_classification(self) -> dict[str, Any]:
        """Todos los atributos de la fila más su tipo y estado."""
        return {**self.item, "tipo": self.tipo, "estado": self.estado}


@dataclass
class NotificationTimeline:
    notification_id: str
    rows: list[TimelineRow]

    @property
    def first(self) -> Item:
        return self.rows[0].item

    @property
    def rescheduled(self) -> bool:
        return len(self.rows) > 1

    def as_dict(self) -> dict[str, Any]:
        first = self.first
        return {
            "notification_id": self.notification_id,
            "campaign_id": first.get("campaign_id"),
            "app_id": first.get("app_id"),
            "user": first.get("user"),
            "channel": first.get("channel"),
            "filas": [row.summary() for row in self.rows],
        }


def classify_rows(rows: Iterable[Mapping[str, Any]], now: datetime) -> list[NotificationTimeline]:
    """Agrupa por notification_id, ordena por datetime y marca tipo y estado de cada fila."""
    groups: dict[str, list[Item]] = {}
    for row in rows:
        groups.setdefault(str(row.get(CAMPAIGN_SK, "")), []).append(dict(row))

    timelines: list[NotificationTimeline] = []
    for notification_id, items in groups.items():
        items.sort(key=lambda item: str(item.get(CAMPAIGN_PK, "")))
        classified: list[TimelineRow] = []
        previous: int | None = None
        for item in items:
            retries = parse_retries(item.get("retries"))
            if previous is None:
                tipo = RowType.ORIGINAL
            elif retries > previous:
                tipo = RowType.REINTENTO
            else:
                tipo = RowType.FUERA_DE_HORARIO
            previous = retries
            state = row_state(str(item.get(CAMPAIGN_PK, "")), now)
            classified.append(TimelineRow(item, tipo, state))
        timelines.append(NotificationTimeline(notification_id, classified))
    timelines.sort(
        key=lambda timeline: (timeline.rows[0].datetime, str(timeline.first.get("user")))
    )
    return timelines


@dataclass
class RowStats:
    usuarios: int = 0
    filas: int = 0
    notificaciones: int = 0
    reprogramados: int = 0
    fuera_de_horario: int = 0
    reintentos: int = 0
    pendientes: int = 0
    en_curso: int = 0

    def as_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


def summarize(timelines: Iterable[NotificationTimeline]) -> RowStats:
    stats = RowStats()
    users: set[str] = set()
    types: Counter[RowType] = Counter()
    states: Counter[RowState] = Counter()
    for timeline in timelines:
        stats.notificaciones += 1
        stats.filas += len(timeline.rows)
        stats.reprogramados += int(timeline.rescheduled)
        users.add(str(timeline.first.get("user")))
        types.update(row.tipo for row in timeline.rows)
        states.update(row.estado for row in timeline.rows)
    stats.usuarios = len(users)
    stats.fuera_de_horario = types[RowType.FUERA_DE_HORARIO]
    stats.reintentos = types[RowType.REINTENTO]
    stats.pendientes = states[RowState.PENDIENTE]
    stats.en_curso = states[RowState.EN_CURSO]
    return stats


# --- dynamo history ---


@dataclass
class HistoryWindow:
    """Ventana de la tabla de logs (UTC)."""

    start: datetime
    end: datetime | None = None
    app_id: str | None = None
    limit: int | None = None


@dataclass
class LoadHistory:
    entry: LogEntry
    timelines: list[NotificationTimeline] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        entry = self.entry
        stats = summarize(self.timelines)
        return {
            "fecha_utc": entry.datetime,
            "app_id": entry.app_id,
            "estado": entry.status,
            "procesados": entry.total,
            "exitosos": entry.successful,
            "omitidos": entry.omitted,
            "errores": entry.errors,
            "campaign_id": entry.campaign_id,
            "archivo": entry.file,
            "filas": stats.filas,
            "notificaciones": stats.notificaciones,
            "reprogramados": stats.reprogramados,
            "pendientes": stats.pendientes,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.summary(), "detalle_errores": self.entry.error_details}


@dataclass
class HistoryResult:
    loads: list[LoadHistory]
    scanned: bool = False
    truncated: bool = False


def _has_rows(entry: LogEntry) -> bool:
    """Las cargas FAILED o sin campaign_id no dejaron filas en la tabla de campañas."""
    return bool(entry.campaign_id) and entry.status != FAILED_STATUS


def load_history(
    logs: LogsTable, campaigns: CampaignsTable, window: HistoryWindow, now: datetime
) -> HistoryResult:
    """Cargas de la ventana con sus filas de campañas (un scan para todos los campaign_id)."""
    if window.app_id:
        found = logs.by_app(window.app_id, window.start, window.end, limit=window.limit)
    else:
        found = logs.recent(window.start, window.end, limit=window.limit)
    entries = [parse_log_entry(item) for item in found.items]
    campaign_ids = [str(entry.campaign_id) for entry in entries if _has_rows(entry)]
    rows = campaigns.by_campaigns(campaign_ids)

    by_campaign: dict[str, list[Item]] = {}
    for item in rows.items:
        by_campaign.setdefault(str(item.get("campaign_id")), []).append(item)
    loads = [
        LoadHistory(
            entry,
            classify_rows(by_campaign.get(str(entry.campaign_id), []), now)
            if _has_rows(entry)
            else [],
        )
        for entry in entries
    ]
    return HistoryResult(loads, scanned=found.scanned or rows.scanned, truncated=found.truncated)


# --- dynamo campaign ---


@dataclass
class CampaignDetail:
    campaign_id: str
    loads: list[LogEntry]
    timelines: list[NotificationTimeline]
    scanned: bool = False

    @property
    def found(self) -> bool:
        return bool(self.loads or self.timelines)

    @property
    def stats(self) -> RowStats:
        return summarize(self.timelines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "cargas": [entry.as_dict() for entry in self.loads],
            "notificaciones": [timeline.as_dict() for timeline in self.timelines],
            "resumen": self.stats.as_dict(),
        }


def campaign_detail(
    logs: LogsTable, campaigns: CampaignsTable, campaign_id: str, now: datetime
) -> CampaignDetail:
    """La carga (o cargas) de un CSV en logs y la línea de tiempo de cada notification_id."""
    loads = logs.by_campaign(campaign_id)
    rows = campaigns.find(campaign_id=campaign_id)
    return CampaignDetail(
        campaign_id=campaign_id,
        loads=[parse_log_entry(item) for item in loads.items],
        timelines=classify_rows(rows.items, now),
        scanned=loads.scanned or rows.scanned,
    )
