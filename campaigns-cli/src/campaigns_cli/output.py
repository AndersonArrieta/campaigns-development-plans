"""Salida de la CLI: datos en stdout (tabla o JSON) y mensajes en stderr.

En modo JSON, stdout solo contiene JSON válido para poder encadenarlo con `jq`.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from campaigns_cli.settings import OutputFormat

console = Console()
err_console = Console(stderr=True)

STATUS_STYLES = {
    "OK": "green",
    "OPCIONAL": "yellow",
    "OMITIDA": "yellow",
    "FALTA CONFIG": "red",
    "NO EXISTE": "red",
    "SIN PERMISO": "red",
    "ERROR": "red",
    "FALLA": "red",
}

Row = Mapping[str, Any]


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set | frozenset):
        return sorted(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    raise TypeError(f"Tipo no serializable: {type(value).__name__}")


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, list | tuple):
        return ", ".join(str(item) for item in value)
    if isinstance(value, Enum):
        value = value.value
    text = escape(str(value))
    style = STATUS_STYLES.get(str(value))
    return f"[{style}]{text}[/{style}]" if style else text


def _header(key: str) -> str:
    return key.replace("_", " ").capitalize()


def render(
    data: Row | Sequence[Row],
    output: OutputFormat,
    *,
    title: str | None = None,
    columns: Sequence[str] | None = None,
) -> None:
    """Muestra un registro (clave/valor) o una lista de registros (una fila por registro)."""
    if output is OutputFormat.JSON:
        console.out(to_json(data), highlight=False)
        return

    table = Table(title=title)
    if isinstance(data, Mapping):
        table.add_column("Campo", style="cyan")
        table.add_column("Valor", overflow="fold")
        for key, value in data.items():
            table.add_row(_header(key), _cell(value))
        console.print(table)
        return

    if not data:
        info("Sin resultados.")
        return
    keys = list(columns) if columns else list(data[0].keys())
    for key in keys:
        # fold: los IDs y ARNs largos se parten en varias líneas en lugar de recortarse con "…"
        table.add_column(_header(key), overflow="fold")
    for row in data:
        table.add_row(*(_cell(row.get(key)) for key in keys))
    console.print(table)


def info(message: str) -> None:
    err_console.print(escape(message))


def success(message: str) -> None:
    err_console.print(f"[green]✓[/green] {escape(message)}")


def warn(message: str) -> None:
    err_console.print(f"[yellow]![/yellow] {escape(message)}")


def fail(message: str) -> None:
    err_console.print(f"[red]✗ {escape(message)}[/red]")
