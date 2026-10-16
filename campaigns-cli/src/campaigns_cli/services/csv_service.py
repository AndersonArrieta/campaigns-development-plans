"""Generación y validación de los CSV de campaña que procesa ingester_Lambda (sin AWS).

Reglas tomadas del ingester (repo `NU0284001_Artemis_Chatbots_Platform_MR`):

- `ingester_Lambda/src/libs/source_data_management.py`:
    - `read_data`: `csv.DictReader(delimiter=";", skipinitialspace=True, quoting=QUOTE_NONE)`;
      `retrieve_data_file` decodifica con `utf-8-sig` (acepta BOM).
    - `structure_fields_validation`: los 9 campos deben estar en el encabezado (no exige orden).
    - `app_id_validation` (no vacío, mínimo 2 caracteres), `canal_validation` (`msteams`, `email`,
      `sms`, `push`, `whatsapp`, sin distinguir mayúsculas), `user_validation` (email o teléfono,
      con `re.match`, sin importar el canal), `dates_validation` (`dd/mm/aaaa`, `fecha_fin` no
      anterior a hoy en Colombia ni a `fecha_inicio`), `days_validation` (separados por `,`, en
      español sin tildes o en inglés), `hours_validation` (separadas por `,`, 0-23),
      `node_validation` (`re.match("(N-\\d\\d-\\d\\d-\\d\\d)", IGNORECASE)`) y
      `parameters_validation` (opcional, `clave:valor` separados por `,`, sin espacios en la clave).
- `ingester_Conf/ingester.yaml`: `csv_fields`, `week_days`, `email_eval_regex` y
  `phone_number_eval_regex` (`^[0-9]{11,12}$`).
- `ingester_Lambda/src/models/notification.py` (`_datetime_arrangement`, `_apply_date_format`):
  las fechas del rango que no caen en `dias` y las horas anteriores a la hora en punto actual se
  omiten sin error. Aquí se informan como avisos.
- `ingester_Lambda/src/controllers/processor.py` (`_rows_process`): las filas se numeran desde 2
  (la 1 es el encabezado).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import astuple, dataclass, fields
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from campaigns_cli.errors import UsageError

# Carpeta de los CSV de prueba, relativa a `campaigns-cli/` (donde se ejecuta la CLI).
DATA_DIR = Path("data")

DELIMITER = ";"
FIELDS = (
    "app_id",
    "canal",
    "usuario",
    "fecha_inicio",
    "fecha_fin",
    "dias",
    "horas",
    "nodo",
    "parametros",
)
CHANNELS = ("msteams", "email", "sms", "push", "whatsapp")
# `week_days` del ingester: español sin tildes → inglés. Orden de `date.weekday()`.
WEEK_DAYS = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "domingo": "sunday",
}
DATE_FORMAT = "%d/%m/%Y"
PHONE_RE = re.compile(r"^[0-9]{11,12}$")
EMAIL_RE = re.compile(
    r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b"""
    r"""\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9]"""
    r"""(?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4]"""
    r"""[0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?"""
    r"""[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01"""
    r"""-\x09\x0b\x0c\x0e-\x7f])+)\])"""
)
NODE_RE = re.compile(r"(N-\d\d-\d\d-\d\d)", re.IGNORECASE)

_RELATIVE_DATES = {"hoy": 0, "mañana": 1, "manana": 1}


class Severity(StrEnum):
    ERROR = "ERROR"
    AVISO = "AVISO"


@dataclass(frozen=True)
class ValidationIssue:
    """Problema de un CSV. `row` es la línea del archivo (1 = encabezado); None = el archivo."""

    row: int | None
    column: str | None
    message: str
    severity: Severity = Severity.ERROR

    def as_dict(self) -> dict[str, Any]:
        return {
            "fila": self.row,
            "columna": self.column,
            "severidad": self.severity,
            "mensaje": self.message,
        }


@dataclass(frozen=True)
class CampaignRow:
    """Una fila del CSV, con los valores tal como se escriben."""

    app_id: str
    canal: str
    usuario: str
    fecha_inicio: str
    fecha_fin: str
    dias: str
    horas: str
    nodo: str
    parametros: str = ""

    def as_dict(self) -> dict[str, str]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


# --- Generación ---


def parse_fecha(value: str, today: date) -> date:
    """`dd/mm/aaaa`, `hoy` o `mañana` (hora Colombia)."""
    text = value.strip().lower()
    if text in _RELATIVE_DATES:
        return today + timedelta(days=_RELATIVE_DATES[text])
    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise UsageError(f"Fecha inválida '{value}': usa dd/mm/aaaa, 'hoy' o 'mañana'.") from None


def parse_horas(value: str, now: datetime) -> list[int]:
    """Horas separadas por `,` (0-23) o `+N`: hora actual de Colombia + N."""
    hours: list[int] = []
    for part in (item.strip() for item in value.split(",")):
        if not part:
            continue
        try:
            hour = now.hour + int(part[1:]) if part.startswith("+") else int(part)
        except ValueError:
            raise UsageError(f"Hora inválida '{part}': usa 0-23 o +N.") from None
        if not 0 <= hour <= 23:
            raise UsageError(f"La hora '{part}' da {hour}: debe quedar entre 0 y 23.")
        hours.append(hour)
    if not hours:
        raise UsageError("Indica al menos una hora con --hora.")
    return sorted(set(hours))


def parse_parametros(values: Sequence[str]) -> str:
    """`clave=valor` o `clave:valor` → `clave:valor,clave:valor` (formato del ingester)."""
    pairs = []
    for value in values:
        for item in (part.strip() for part in value.split(",")):
            if not item:
                continue
            key, sep, val = item.replace("=", ":", 1).partition(":")
            if not sep or not key.strip() or not val.strip() or re.search(r"\s", key.strip()):
                raise UsageError(
                    f"Parámetro inválido '{item}': usa clave=valor (clave sin espacios)."
                )
            pairs.append(f"{key.strip()}:{val.strip()}")
    return ",".join(pairs)


def weekdays_between(start: date, end: date) -> list[str]:
    """Días de la semana (en español) que aparecen entre dos fechas, de lunes a domingo."""
    names = list(WEEK_DAYS)
    present = {
        (start + timedelta(days=offset)).weekday() for offset in range((end - start).days + 1)
    }
    return [names[index] for index in sorted(present)]


def generate_rows(
    users: Sequence[str],
    *,
    canal: str,
    start: date,
    end: date,
    hours: Sequence[int],
    nodo: str,
    app_id: str,
    dias: Sequence[str] | None = None,
    parametros: str = "",
) -> list[CampaignRow]:
    """Una fila por usuario. Sin `dias`, los días de la semana del rango de fechas."""
    if end < start:
        raise UsageError("--fecha-fin no puede ser anterior a --fecha.")
    if not users:
        raise UsageError("Indica al menos un usuario con --users.")
    days = list(dias) if dias else weekdays_between(start, end)
    return [
        CampaignRow(
            app_id=app_id,
            canal=canal,
            usuario=user,
            fecha_inicio=start.strftime(DATE_FORMAT),
            fecha_fin=end.strftime(DATE_FORMAT),
            dias=",".join(days),
            horas=",".join(str(hour) for hour in hours),
            nodo=nodo,
            parametros=parametros,
        )
        for user in users
    ]


def render_csv(rows: Iterable[CampaignRow]) -> str:
    """Texto del CSV: separador `;`, sin comillas (el ingester lee con QUOTE_NONE), salto `\\n`."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer, delimiter=DELIMITER, quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n"
    )
    writer.writerow(FIELDS)
    for row in rows:
        values = astuple(row)
        if any(DELIMITER in value or "\n" in value for value in values):
            raise UsageError(f"Un valor contiene '{DELIMITER}' o un salto de línea: {values}")
        writer.writerow(values)
    return buffer.getvalue()


def write_csv(rows: Iterable[CampaignRow], path: Path) -> Path:
    """Escribe el CSV en UTF-8 sin BOM, creando la carpeta si no existe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_csv(rows), encoding="utf-8", newline="")
    return path


def default_output(now: datetime) -> Path:
    return DATA_DIR / f"campaign-{now:%Y%m%d-%H%M%S}.csv"


def resolve_csv_path(value: str | Path) -> Path:
    """La ruta tal cual si existe; si no, dentro de `data/`."""
    path = Path(value)
    if path.is_file():
        return path
    candidate = DATA_DIR / path
    if not path.is_absolute() and candidate.is_file():
        return candidate
    raise UsageError(f"No existe el archivo '{value}' (ni en {DATA_DIR}/).")


# --- Validación ---


def validate_csv(path: Path, now: datetime) -> list[ValidationIssue]:
    """Valida un archivo como lo haría el ingester. `now` es la hora actual de Colombia."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return [ValidationIssue(None, None, f"El archivo no está en UTF-8: {exc}.")]
    return validate_text(text, now)


def validate_text(text: str, now: datetime) -> list[ValidationIssue]:
    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=DELIMITER,
        skipinitialspace=True,
        quoting=csv.QUOTE_NONE,
    )
    lines = [(reader.line_num, values) for values in reader if values]
    if not lines:
        return [ValidationIssue(None, None, "El archivo está vacío.")]

    header = lines[0][1]
    issues = _header_issues(header)
    if any(issue.severity is Severity.ERROR for issue in issues):
        return issues
    if len(lines) == 1:
        return [*issues, ValidationIssue(None, None, "El archivo no tiene filas de datos.")]

    for line_number, values in lines[1:]:
        if len(values) < len(header):
            issues.append(
                ValidationIssue(
                    line_number,
                    None,
                    f"La fila tiene {len(values)} columnas y el encabezado {len(header)}: "
                    "el ingester falla con todo el archivo.",
                )
            )
            continue
        if len(values) > len(header):
            issues.append(
                ValidationIssue(
                    line_number,
                    None,
                    f"La fila tiene {len(values)} columnas y el encabezado {len(header)}; "
                    "las sobrantes se ignoran.",
                    Severity.AVISO,
                )
            )
        row = dict(zip(header, values, strict=False))
        issues.extend(validate_row(line_number, row, now))
    return issues


def _header_issues(header: Sequence[str]) -> list[ValidationIssue]:
    if len(header) == 1 and "," in header[0]:
        return [ValidationIssue(1, None, f"El separador debe ser '{DELIMITER}', no ','.")]
    missing = [name for name in FIELDS if name not in header]
    if missing:
        return [ValidationIssue(1, name, "Falta la columna en el encabezado.") for name in missing]
    issues = []
    extra = [name for name in header if name not in FIELDS]
    if extra:
        issues.append(
            ValidationIssue(
                1, None, f"Columnas extra ignoradas: {', '.join(extra)}.", Severity.AVISO
            )
        )
    if [name for name in header if name in FIELDS] != list(FIELDS):
        issues.append(
            ValidationIssue(
                1,
                None,
                f"Las columnas no están en el orden de referencia ({DELIMITER.join(FIELDS)}); "
                "el ingester lo acepta.",
                Severity.AVISO,
            )
        )
    return issues


def validate_row(line: int, row: Mapping[str, str], now: datetime) -> list[ValidationIssue]:
    """Reglas por columna del ingester, más avisos de lo que omitiría sin error."""
    issues: list[ValidationIssue] = []

    def error(column: str, message: str) -> None:
        issues.append(ValidationIssue(line, column, message))

    app_id = row["app_id"].strip()
    if not app_id:
        error("app_id", "El app_id no puede estar vacío.")
    elif len(app_id) < 2:
        error("app_id", f"El app_id '{app_id}' es muy corto (mínimo 2 caracteres).")

    canal = row["canal"].strip()
    if not canal:
        error("canal", "El canal no puede estar vacío.")
    elif canal.lower() not in CHANNELS:
        error("canal", f"Canal inválido '{canal}'. Válidos: {', '.join(CHANNELS)}.")

    usuario = row["usuario"]
    if not EMAIL_RE.match(usuario) and not PHONE_RE.match(usuario):
        error(
            "usuario",
            f"Usuario inválido '{usuario}': teléfono de 11 o 12 dígitos con indicativo o email "
            "en minúscula.",
        )

    start = _parse_date(row["fecha_inicio"])
    end = _parse_date(row["fecha_fin"])
    if start is None:
        error("fecha_inicio", f"Fecha inválida '{row['fecha_inicio']}': debe ser dd/mm/aaaa.")
    if end is None:
        error("fecha_fin", f"Fecha inválida '{row['fecha_fin']}': debe ser dd/mm/aaaa.")
    if start is not None and end is not None:
        if end < start:
            error("fecha_fin", f"fecha_fin {row['fecha_fin']} es anterior a fecha_inicio.")
        elif end < now.date():
            error("fecha_fin", f"fecha_fin {row['fecha_fin']} está en el pasado (hora Colombia).")

    weekdays = _parse_days(row["dias"])
    if weekdays is None:
        error("dias", f"Días inválidos '{row['dias']}': al menos uno, separados por ','.")
    elif bad_days := [day for day, number in weekdays if number is None]:
        error(
            "dias",
            f"Días inválidos {', '.join(repr(day) for day in bad_days)}: en español sin tildes "
            "(lunes…domingo) o en inglés.",
        )

    hours = _parse_hours(row["horas"])
    if hours is None:
        error("horas", f"Horas inválidas '{row['horas']}': al menos una, separadas por ','.")
    elif bad_hours := [text for text, value in hours if value is None]:
        error(
            "horas",
            f"Horas inválidas {', '.join(repr(hour) for hour in bad_hours)}: enteros entre 0 y 23.",
        )

    if not NODE_RE.match(row["nodo"].strip()):
        error("nodo", f"Nodo inválido '{row['nodo']}': formato N-00-00-00.")

    if bad_params := _invalid_parameters(row["parametros"]):
        error(
            "parametros",
            f"Parámetros inválidos {', '.join(repr(param) for param in bad_params)}: "
            "formato clave:valor separados por ',', sin espacios en la clave.",
        )

    if issues or start is None or end is None or weekdays is None or hours is None:
        return issues
    days = {number for _, number in weekdays if number is not None}
    valid_hours = [value for _, value in hours if value is not None]
    issues.extend(_schedule_warnings(line, start, end, days, valid_hours, now))
    return issues


def _schedule_warnings(
    line: int, start: date, end: date, days: set[int], hours: list[int], now: datetime
) -> list[ValidationIssue]:
    """Lo que el ingester omite sin error: días fuera del rango y horas ya pasadas."""
    first = max(start, now.date())
    dates = [
        first + timedelta(days=offset)
        for offset in range((end - first).days + 1)
        if (first + timedelta(days=offset)).weekday() in days
    ]
    if not dates:
        return [
            ValidationIssue(
                line,
                "dias",
                "Ninguna fecha desde hoy hasta fecha_fin cae en esos días: el ingester no creará "
                "filas.",
                Severity.AVISO,
            )
        ]
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    future = [
        moment
        for day in dates
        for hour in hours
        if (moment := datetime.combine(day, datetime.min.time()) + timedelta(hours=hour))
        >= current_hour
    ]
    if not future:
        return [
            ValidationIssue(
                line,
                "horas",
                f"Todas las horas ya pasaron (son las {now:%H:%M} en Colombia): el ingester no "
                "creará filas.",
                Severity.AVISO,
            )
        ]
    return []


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).date()
    except ValueError:
        return None


def _parse_days(value: str) -> list[tuple[str, int | None]] | None:
    parts = value.split(",")
    if parts[0] == "":
        return None
    names = list(WEEK_DAYS)
    english = list(WEEK_DAYS.values())
    result: list[tuple[str, int | None]] = []
    for part in parts:
        day = part.lower().strip()
        number = (
            names.index(day) if day in names else english.index(day) if day in english else None
        )
        result.append((part.strip(), number))
    return result


def _parse_hours(value: str) -> list[tuple[str, int | None]] | None:
    parts = value.split(",")
    if parts[0] == "":
        return None
    result: list[tuple[str, int | None]] = []
    for part in parts:
        text = part.strip()
        try:
            number: int | None = int(text)
        except ValueError:
            number = None
        if number is not None and not 0 <= number <= 23:
            number = None
        result.append((text, number))
    return result


def _invalid_parameters(value: str) -> list[str]:
    parts = value.split(",")
    if parts[0].strip() == "":
        return []
    invalid = []
    for part in parts:
        pieces = part.split(":")
        if (
            len(pieces) < 2
            or re.search(r"\s", pieces[0].strip())
            or not pieces[0].strip()
            or not pieces[1].strip()
        ):
            invalid.append(part.strip())
    return invalid


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(issue.severity is Severity.ERROR for issue in issues)
