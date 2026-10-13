"""Fechas y horas: zonas de las tablas, parseo de `--since` y de fechas de la línea de comandos."""

import re
from datetime import UTC, datetime, timedelta, timezone

from campaigns_cli.errors import UsageError

# Las fechas de la tabla de campañas están en hora Colombia (UTC-5), la usada por el ingester
# y el scheduler. Las de la tabla de logs salen de `datetime.now()` en la Lambda (UTC).
COLOMBIA_TZ = timezone(timedelta(hours=-5))

DYNAMO_FORMAT = "%Y-%m-%d %H:%M:%S"

_SINCE_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_SINCE_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H",
    "%Y-%m-%d",
)


def colombia_now() -> datetime:
    """Hora actual de Colombia, sin zona (igual que las fechas guardadas en la tabla)."""
    return datetime.now(COLOMBIA_TZ).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def parse_since(value: str) -> timedelta:
    """Convierte `30s`, `15m`, `2h` o `1d` en un timedelta."""
    match = _SINCE_PATTERN.match(value)
    if not match:
        raise UsageError(f"Valor inválido '{value}': usa un número y s, m, h o d (ej. 2h).")
    amount, unit = int(match.group(1)), match.group(2).lower()
    return timedelta(**{_SINCE_UNITS[unit]: amount})


def parse_datetime(value: str) -> datetime:
    """Acepta `YYYY-MM-DD`, `YYYY-MM-DD HH`, `YYYY-MM-DD HH:MM` y `YYYY-MM-DD HH:MM:SS`."""
    text = value.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise UsageError(f"Fecha inválida '{value}': usa YYYY-MM-DD o 'YYYY-MM-DD HH:MM:SS'.")


def to_dynamo(value: datetime) -> str:
    return value.strftime(DYNAMO_FORMAT)


def hour_floor(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)
