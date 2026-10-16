"""Vaciado de las tablas de campañas y de logs, completo o solo de lo que dejó un CSV.

Las tablas de dev son de uso exclusivo de las pruebas (ADR-0011). El borrado es por clave:
scan paginado con `ProjectionExpression` y `batch_write_item` (`delete_keys`, de T-012). No se
usan `DeleteTable`/`CreateTable`: se perderían el TTL, los streams y los permisos de la tabla.

Al terminar, un scan de verificación cuenta las filas que quedaron; las que el ingester o el ms
escriban durante el borrado pueden quedar.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from campaigns_cli.services.dynamo_service import (
    CampaignsTable,
    Item,
    LogsTable,
    delete_keys,
    key_of,
)
from campaigns_cli.services.history_service import RowState, RowType, classify_rows


class TableChoice(StrEnum):
    CAMPAIGNS = "campaigns"
    LOGS = "logs"
    ALL = "all"

    @property
    def includes_campaigns(self) -> bool:
        return self in (TableChoice.CAMPAIGNS, TableChoice.ALL)

    @property
    def includes_logs(self) -> bool:
        return self in (TableChoice.LOGS, TableChoice.ALL)


@dataclass
class TablePlan:
    table: str
    source: CampaignsTable | LogsTable
    rows: list[Item]
    scanned: bool = False
    rescheduled: int = 0
    pending: int = 0
    in_progress: int = 0

    @property
    def table_name(self) -> str:
        return self.source.table_name

    @property
    def by_app(self) -> dict[str, int]:
        counts = Counter(str(row.get("app_id", "")) for row in self.rows)
        return dict(sorted(counts.items()))

    def summary(self) -> dict[str, Any]:
        return {
            "tabla": self.table,
            "nombre": self.table_name,
            "filas": len(self.rows),
            "reprogramadas": self.rescheduled,
            "pendientes": self.pending,
            "en_curso": self.in_progress,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.summary(), "por_app_id": self.by_app}


@dataclass
class CleanPlan:
    campaign_id: str | None
    tables: list[TablePlan] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(table.rows) for table in self.tables)

    @property
    def in_progress(self) -> int:
        return sum(table.in_progress for table in self.tables)

    @property
    def scanned(self) -> bool:
        return any(table.scanned for table in self.tables)

    def by_app_rows(self) -> list[dict[str, Any]]:
        return [
            {"tabla": table.table, "app_id": app_id, "filas": count}
            for table in self.tables
            for app_id, count in table.by_app.items()
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "tablas": [table.as_dict() for table in self.tables],
        }


def plan_clean(
    campaigns: CampaignsTable | None,
    logs: LogsTable | None,
    now: datetime,
    campaign_id: str | None = None,
) -> CleanPlan:
    """Filas a borrar por tabla: todas, o solo las de `campaign_id` (incluidas reprogramaciones)."""
    plan = CleanPlan(campaign_id)
    if campaigns is not None:
        found = campaigns.keys(campaign_id)
        table_plan = TablePlan("campaigns", campaigns, found.items, scanned=found.scanned)
        for timeline in classify_rows(found.items, now):
            for row in timeline.rows:
                table_plan.rescheduled += int(row.tipo is not RowType.ORIGINAL)
                table_plan.pending += int(row.estado is RowState.PENDIENTE)
                table_plan.in_progress += int(row.estado is RowState.EN_CURSO)
        plan.tables.append(table_plan)
    if logs is not None:
        found = logs.keys(campaign_id)
        plan.tables.append(TablePlan("logs", logs, found.items, scanned=found.scanned))
    return plan


@dataclass
class TableResult:
    table: str
    table_name: str
    deleted: int
    failed: int
    remaining: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "tabla": self.table,
            "nombre": self.table_name,
            "borradas": self.deleted,
            "fallidas": self.failed,
            "restantes": self.remaining,
        }


@dataclass
class CleanResult:
    tables: list[TableResult]

    @property
    def ok(self) -> bool:
        return all(not table.failed and not table.remaining for table in self.tables)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [table.as_dict() for table in self.tables]


def _belongs(source: CampaignsTable | LogsTable, row: Mapping[str, Any], campaign_id: str) -> bool:
    return source.campaign_of(row) == campaign_id


def execute(plan: CleanPlan, *, sleep: Callable[[float], None] = time.sleep) -> CleanResult:
    """Borra las filas del plan y verifica con un scan cuántas quedaron."""
    results: list[TableResult] = []
    for table in plan.tables:
        source = table.source
        rows = table.rows
        if plan.campaign_id is not None:
            # Se vuelve a comprobar cada fila aunque el scan ya haya filtrado por campaign_id.
            rows = [row for row in rows if _belongs(source, row, plan.campaign_id)]
        keys = [key_of(row, source.key_names) for row in rows]
        deleted = delete_keys(source.client, source.table_name, keys, sleep=sleep)
        remaining = len(source.keys(plan.campaign_id).items)
        results.append(
            TableResult(
                table=table.table,
                table_name=table.table_name,
                deleted=deleted.deleted,
                failed=deleted.failed,
                remaining=remaining,
            )
        )
    return CleanResult(results)
