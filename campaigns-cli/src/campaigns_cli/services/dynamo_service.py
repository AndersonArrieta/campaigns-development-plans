"""Lectura de las tablas DynamoDB de campañas y de logs de ejecución del ingester.

Esquemas (tomados de ingester_Lambda y scheduler_Lambda):

Tabla de campañas (`CAMPAIGNS_TABLE_NAME`), la escribe el ingester y la lee el scheduler:
    - PK `datetime`: hora programada `YYYY-MM-DD HH:00:00`, hora Colombia.
    - SK `notification_id`: UUID por usuario y fecha/hora.
    - Atributos: `campaign_id` (UUID por archivo), `app_id`, `channel`, `user`,
      `notification_node`, `retries`, `context` (mapa), `expiration_date` (TTL, epoch).
    - Sin índices secundarios: buscar por `campaign_id` o `user` requiere scan,
      salvo que se configure un GSI en `CAMPAIGNS_TABLE_CAMPAIGN_INDEX`.

Tabla de logs (`CAMPAIGNS_LOGS_TABLE_NAME`), un registro por archivo procesado:
    - PK `app_id` (`UNKNOWN` si el archivo no se pudo leer).
    - SK `datetime`: `str(datetime.now())` de la Lambda, ej. `2026-10-13 15:04:05.123456`.
    - `result`: JSON en texto con `status`, `stats` y `body_result` (de ahí salen
      `campaign_id` y la key del archivo).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from boto3.dynamodb.types import TypeDeserializer

from campaigns_cli.errors import UsageError
from campaigns_cli.timeutils import hour_floor, to_dynamo

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

CAMPAIGN_PK = "datetime"
CAMPAIGN_SK = "notification_id"
LOGS_PK = "app_id"
LOGS_SK = "datetime"

# Un mes de particiones horarias: evita miles de consultas por un rango mal escrito.
MAX_HOURS = 24 * 31

_deserializer = TypeDeserializer()

Item = dict[str, Any]


def deserialize(raw: Mapping[str, Any]) -> Item:
    return {key: _deserializer.deserialize(value) for key, value in raw.items()}


@dataclass
class QueryResult:
    items: list[Item]
    scanned: bool = False
    truncated: bool = False


def _filter_expression(filters: Mapping[str, str | None]) -> dict[str, Any]:
    """Arma FilterExpression con alias (`user` y `datetime` son palabras reservadas)."""
    active = {name: value for name, value in filters.items() if value}
    if not active:
        return {}
    names: dict[str, str] = {}
    values: dict[str, Any] = {}
    parts = []
    for index, (name, value) in enumerate(active.items()):
        names[f"#f{index}"] = name
        values[f":f{index}"] = {"S": value}
        parts.append(f"#f{index} = :f{index}")
    return {
        "FilterExpression": " AND ".join(parts),
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }


def _merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    """Combina kwargs de una consulta, uniendo alias y valores de expresiones."""
    merged = dict(base)
    for key, value in extra.items():
        if key in ("ExpressionAttributeNames", "ExpressionAttributeValues"):
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = value
    return merged


def _iterate(call: Callable[..., Any], kwargs: dict[str, Any]) -> Iterator[Item]:
    """Recorre todas las páginas de un query o scan."""
    request = dict(kwargs)
    while True:
        response = call(**request)
        for raw in response.get("Items", []):
            yield deserialize(raw)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return
        request["ExclusiveStartKey"] = last_key


def _collect(items: Iterator[Item], limit: int | None) -> tuple[list[Item], bool]:
    collected: list[Item] = []
    for item in items:
        if limit is not None and len(collected) >= limit:
            return collected, True
        collected.append(item)
    return collected, False


class CampaignsTable:
    def __init__(
        self, client: DynamoDBClient, table_name: str, campaign_index: str | None = None
    ) -> None:
        self.client = client
        self.table_name = table_name
        self.campaign_index = campaign_index

    def get(self, notification_id: str, scheduled: str | None = None) -> QueryResult:
        """Busca un registro. Con la fecha programada es un get_item; sin ella, un scan."""
        if scheduled:
            response = self.client.get_item(
                TableName=self.table_name,
                Key={CAMPAIGN_PK: {"S": scheduled}, CAMPAIGN_SK: {"S": notification_id}},
            )
            raw = response.get("Item")
            return QueryResult([deserialize(raw)] if raw else [])
        kwargs = _merge(
            {"TableName": self.table_name},
            _filter_expression({CAMPAIGN_SK: notification_id}),
        )
        items, _ = _collect(_iterate(self.client.scan, kwargs), limit=1)
        return QueryResult(items, scanned=True)

    def find(
        self,
        *,
        campaign_id: str | None = None,
        user: str | None = None,
        app_id: str | None = None,
        limit: int | None = None,
    ) -> QueryResult:
        """Busca por campaign_id, usuario y/o app_id (query sobre el GSI o scan filtrado)."""
        if campaign_id and self.campaign_index:
            kwargs = _merge(
                {
                    "TableName": self.table_name,
                    "IndexName": self.campaign_index,
                    "KeyConditionExpression": "#pk = :pk",
                    "ExpressionAttributeNames": {"#pk": "campaign_id"},
                    "ExpressionAttributeValues": {":pk": {"S": campaign_id}},
                },
                _filter_expression({"user": user, "app_id": app_id}),
            )
            items, truncated = _collect(_iterate(self.client.query, kwargs), limit)
            return QueryResult(_sort_campaigns(items), truncated=truncated)

        kwargs = _merge(
            {"TableName": self.table_name},
            _filter_expression({"campaign_id": campaign_id, "user": user, "app_id": app_id}),
        )
        items, truncated = _collect(_iterate(self.client.scan, kwargs), limit)
        return QueryResult(_sort_campaigns(items), scanned=True, truncated=truncated)

    def list_range(
        self,
        start: datetime,
        end: datetime,
        *,
        app_id: str | None = None,
        user: str | None = None,
        limit: int | None = None,
    ) -> QueryResult:
        """Lista los registros programados entre dos horas con un query por partición horaria."""
        hours = list(_hours_between(start, end))
        if len(hours) > MAX_HOURS:
            raise UsageError(f"El rango cubre {len(hours)} horas; el máximo es {MAX_HOURS}.")

        def all_hours() -> Iterator[Item]:
            for hour in hours:
                kwargs = _merge(
                    {
                        "TableName": self.table_name,
                        "KeyConditionExpression": "#pk = :pk",
                        "ExpressionAttributeNames": {"#pk": CAMPAIGN_PK},
                        "ExpressionAttributeValues": {":pk": {"S": to_dynamo(hour)}},
                    },
                    _filter_expression({"app_id": app_id, "user": user}),
                )
                yield from _iterate(self.client.query, kwargs)

        items, truncated = _collect(all_hours(), limit)
        return QueryResult(items, truncated=truncated)


def _hours_between(start: datetime, end: datetime) -> Iterator[datetime]:
    current = hour_floor(start)
    last = hour_floor(end)
    while current <= last:
        yield current
        current += timedelta(hours=1)


def _sort_campaigns(items: list[Item]) -> list[Item]:
    return sorted(items, key=lambda item: (str(item.get(CAMPAIGN_PK, "")), str(item.get("user"))))


# --- Tabla de logs ---

_CAMPAIGN_IN_TEXT = re.compile(r"\[Campaign ([^\]]+)\]")
_FILE_IN_TEXT = re.compile(r"with file (\S+)")


@dataclass
class LogEntry:
    app_id: str
    datetime: str
    status: str
    total: int | None = None
    successful: int | None = None
    omitted: int | None = None
    errors: int | None = None
    campaign_id: str | None = None
    file: str | None = None
    error_details: list[Any] = field(default_factory=list)
    result: Any = None

    @property
    def key(self) -> tuple[str, str]:
        return self.app_id, self.datetime

    def summary(self) -> dict[str, Any]:
        return {
            "fecha": self.datetime,
            "app_id": self.app_id,
            "estado": self.status,
            "procesados": self.total,
            "exitosos": self.successful,
            "omitidos": self.omitted,
            "errores": self.errors,
            "campaign_id": self.campaign_id,
            "archivo": self.file,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.summary(), "detalle_errores": self.error_details}


def parse_log_entry(item: Mapping[str, Any]) -> LogEntry:
    """Interpreta un registro de la tabla de logs; tolera `result` vacío o inválido."""
    raw_result = item.get("result")
    result: Any = raw_result
    if isinstance(raw_result, str):
        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError:
            result = raw_result
    payload = result if isinstance(result, dict) else {}
    raw_stats = payload.get("stats")
    stats: dict[str, Any] = raw_stats if isinstance(raw_stats, dict) else {}
    body = payload.get("body_result")

    campaign_id: str | None = None
    file: str | None = None
    details: list[Any] = []
    if isinstance(body, str):
        if match := _CAMPAIGN_IN_TEXT.search(body):
            campaign_id = match.group(1)
        if match := _FILE_IN_TEXT.search(body):
            file = match.group(1)
    elif isinstance(body, dict):
        for key in ("log_errors", "field_validation_errors"):
            entries = body.get(key) or []
            if isinstance(entries, list):
                details.extend(entries)
        for entry in details:
            if isinstance(entry, dict) and entry.get("campaign_id"):
                campaign_id = str(entry["campaign_id"])
                break

    def stat(name: str) -> int | None:
        value = stats.get(name)
        return int(value) if isinstance(value, int | float) else None

    return LogEntry(
        app_id=str(item.get(LOGS_PK, "")),
        datetime=str(item.get(LOGS_SK, "")),
        status=str(payload.get("status", "?")),
        total=stat("total_processed"),
        successful=stat("successful"),
        omitted=stat("omitted"),
        errors=stat("errors"),
        campaign_id=campaign_id,
        file=file,
        error_details=details,
        result=result,
    )


class LogsTable:
    def __init__(self, client: DynamoDBClient, table_name: str) -> None:
        self.client = client
        self.table_name = table_name

    def by_app(
        self,
        app_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> QueryResult:
        """Query por app_id, del más reciente al más antiguo."""
        condition = "#pk = :pk"
        names = {"#pk": LOGS_PK}
        values: dict[str, Any] = {":pk": {"S": app_id}}
        if start or end:
            names["#sk"] = LOGS_SK
            low = to_dynamo(start) if start else "0"
            # "~" ordena después de los dígitos: incluye los microsegundos del último segundo.
            high = f"{to_dynamo(end)}~" if end else "9"
            condition += " AND #sk BETWEEN :low AND :high"
            values[":low"] = {"S": low}
            values[":high"] = {"S": high}
        kwargs = {
            "TableName": self.table_name,
            "KeyConditionExpression": condition,
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
            "ScanIndexForward": False,
        }
        items, truncated = _collect(_iterate(self.client.query, kwargs), limit)
        return QueryResult(items, truncated=truncated)

    def recent(
        self, start: datetime, end: datetime | None = None, limit: int | None = None
    ) -> QueryResult:
        """Registros de todas las apps desde `start` (scan filtrado), del más reciente primero."""
        condition = "#sk >= :low"
        values: dict[str, Any] = {":low": {"S": to_dynamo(start)}}
        if end:
            condition = "#sk BETWEEN :low AND :high"
            values[":high"] = {"S": f"{to_dynamo(end)}~"}
        kwargs = {
            "TableName": self.table_name,
            "FilterExpression": condition,
            "ExpressionAttributeNames": {"#sk": LOGS_SK},
            "ExpressionAttributeValues": values,
        }
        items = sorted(
            _iterate(self.client.scan, kwargs),
            key=lambda item: str(item.get(LOGS_SK, "")),
            reverse=True,
        )
        truncated = limit is not None and len(items) > limit
        selected = items[:limit] if limit is not None else items
        return QueryResult(selected, scanned=True, truncated=truncated)


def follow_logs(
    fetch: Callable[[datetime], list[Item]],
    start: datetime,
    *,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
    max_polls: int | None = None,
) -> Iterator[LogEntry]:
    """Consulta periódicamente y entrega solo los registros nuevos, del más antiguo al más nuevo.

    `fetch(desde)` devuelve los registros con fecha >= desde. Termina con Ctrl+C o tras
    `max_polls` consultas (para pruebas).
    """
    seen: set[tuple[str, str]] = set()
    since = start
    polls = 0
    while max_polls is None or polls < max_polls:
        if polls:
            sleep(interval)
        polls += 1
        entries = sorted(
            (parse_log_entry(item) for item in fetch(since)), key=lambda entry: entry.datetime
        )
        for entry in entries:
            if entry.key in seen:
                continue
            seen.add(entry.key)
            yield entry
        if entries:
            # Se vuelve a pedir el último segundo: `seen` evita duplicados.
            try:
                latest = datetime.strptime(entries[-1].datetime[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            since = max(since, latest)
