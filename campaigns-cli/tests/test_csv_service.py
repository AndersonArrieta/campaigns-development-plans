from datetime import date, datetime
from pathlib import Path

import pytest

from campaigns_cli.errors import UsageError
from campaigns_cli.services.csv_service import (
    DATA_DIR,
    Severity,
    ValidationIssue,
    find_single_csv,
    generate_rows,
    parse_fecha,
    parse_horas,
    parse_parametros,
    render_csv,
    resolve_csv_path,
    validate_csv,
    validate_text,
    weekdays_between,
    write_csv,
)

FIXTURE = Path(__file__).parent / "fixtures" / "csv-test.csv"
# Viernes 16/10/2026, 09:30 en Colombia.
NOW = datetime(2026, 10, 16, 9, 30)
HEADER = "app_id;canal;usuario;fecha_inicio;fecha_fin;dias;horas;nodo;parametros"
VALID = "others-test;WhatsApp;573232540390;16/10/2026;16/10/2026;viernes;10;N-03-99-10;"


def _validate(*lines: str, header: str = HEADER) -> list[ValidationIssue]:
    return validate_text("\n".join([header, *lines]) + "\n", NOW)


def _row(**changes: str) -> str:
    values = dict(zip(HEADER.split(";"), VALID.split(";"), strict=True))
    values.update(changes)
    return ";".join(values.values())


def test_reference_fixture_is_valid() -> None:
    assert validate_csv(FIXTURE, NOW) == []
    assert b"\r\n" in FIXTURE.read_bytes()  # el CSV de referencia viene de Excel (CRLF)


def test_generate_then_validate_round_trip(tmp_path: Path) -> None:
    rows = generate_rows(
        ["573232540390", "573001112233"],
        canal="WhatsApp",
        start=date(2026, 10, 16),
        end=date(2026, 10, 19),
        hours=[10, 15],
        nodo="N-03-99-10",
        app_id="others-test",
        parametros=parse_parametros(["nombre=Ana", "codigo:7"]),
    )
    path = write_csv(rows, tmp_path / "sub" / "campaign.csv")

    assert validate_csv(path, NOW) == []
    content = path.read_text(encoding="utf-8")
    assert content.splitlines()[0] == HEADER
    assert content.splitlines()[1] == (
        "others-test;WhatsApp;573232540390;16/10/2026;19/10/2026;lunes,viernes,sabado,domingo;"
        "10,15;N-03-99-10;nombre:Ana,codigo:7"
    )
    assert not content.startswith("\ufeff")
    assert "\r" not in content


@pytest.mark.parametrize(
    ("text", "row", "column"),
    [
        (VALID.replace(";", ","), 1, None),  # separador ','
        (_row(fecha_inicio="2026-10-13"), 2, "fecha_inicio"),
        (_row(fecha_inicio="20/10/2026", fecha_fin="18/10/2026"), 2, "fecha_fin"),
        (_row(horas="24"), 2, "horas"),
        (_row(dias="martez"), 2, "dias"),
        (_row(nodo="N-3-99-10"), 2, "nodo"),
        (_row(canal="telegram"), 2, "canal"),
        (_row(usuario="3232540390"), 2, "usuario"),  # sin indicativo
        (_row(app_id="x"), 2, "app_id"),
        (_row(parametros="nombre Ana"), 2, "parametros"),
        (_row(fecha_inicio="01/10/2026", fecha_fin="15/10/2026"), 2, "fecha_fin"),  # pasado
    ],
)
def test_one_issue_per_case_with_row_and_column(text: str, row: int, column: str | None) -> None:
    header = HEADER.replace(";", ",") if column is None else HEADER
    issues = _validate(text, header=header)

    assert len(issues) == 1, issues
    assert issues[0].severity is Severity.ERROR
    assert (issues[0].row, issues[0].column) == (row, column)


def test_missing_column_is_one_issue() -> None:
    header = HEADER.replace(";nodo", "")
    issues = _validate(VALID.replace(";N-03-99-10", ""), header=header)

    assert [(issue.row, issue.column) for issue in issues] == [(1, "nodo")]


def test_ingester_accepts_english_days_and_case_insensitive_channels() -> None:
    assert _validate(_row(dias="Friday,lunes", canal="msteams")) == []
    assert _validate(_row(canal="WHATSAPP", nodo="n-03-99-10")) == []


def test_user_email_must_be_lowercase_and_is_channel_independent() -> None:
    assert _validate(_row(canal="msteams", usuario="ana.perez@bancolombia.com.co")) == []
    assert _validate(_row(canal="WhatsApp", usuario="ana@x.co")) == []  # el ingester no lo cruza
    issues = _validate(_row(canal="msteams", usuario="Ana@x.co"))
    assert [issue.column for issue in issues] == ["usuario"]


def test_rows_with_missing_or_extra_columns() -> None:
    issues = _validate(VALID.rsplit(";", 2)[0], VALID + ";extra")

    assert [(issue.row, issue.severity) for issue in issues] == [
        (2, Severity.ERROR),
        (3, Severity.AVISO),
    ]


def test_header_order_and_extra_columns_are_warnings() -> None:
    fields = HEADER.split(";")
    header = ";".join([fields[1], fields[0], *fields[2:], "comentario"])
    values = VALID.split(";")
    issues = _validate(";".join([values[1], values[0], *values[2:], "x"]), header=header)

    assert {issue.severity for issue in issues} == {Severity.AVISO}
    assert len(issues) == 2


def test_warns_when_nothing_would_be_scheduled() -> None:
    no_day = _validate(_row(dias="lunes"))  # 16/10 es viernes
    past_hours = _validate(_row(horas="7,8"))  # son las 09:30
    current_hour = _validate(_row(horas="9"))

    assert [(issue.column, issue.severity) for issue in no_day] == [("dias", Severity.AVISO)]
    assert [(issue.column, issue.severity) for issue in past_hours] == [("horas", Severity.AVISO)]
    assert current_hour == []  # el ingester acepta la hora en curso


def test_file_level_errors(tmp_path: Path) -> None:
    bom = tmp_path / "bom.csv"
    bom.write_bytes(("\ufeff" + HEADER + "\n" + VALID + "\n").encode("utf-8"))
    latin = tmp_path / "latin.csv"
    latin.write_bytes((HEADER + "\n" + _row(app_id="campaña") + "\n").encode("latin-1"))

    assert validate_csv(bom, NOW) == []
    assert "UTF-8" in validate_csv(latin, NOW)[0].message
    assert "vacío" in validate_text("", NOW)[0].message
    assert "filas de datos" in validate_text(HEADER + "\n", NOW)[0].message


def test_parse_fecha() -> None:
    today = date(2026, 10, 16)
    assert parse_fecha("hoy", today) == today
    assert parse_fecha("Mañana", today) == date(2026, 10, 17)
    assert parse_fecha("13/10/2026", today) == date(2026, 10, 13)
    with pytest.raises(UsageError):
        parse_fecha("2026-10-13", today)


def test_parse_horas() -> None:
    assert parse_horas("12,10, 10", NOW) == [10, 12]
    assert parse_horas("+1", NOW) == [10]
    assert parse_horas("+0,+2", NOW) == [9, 11]
    with pytest.raises(UsageError, match="entre 0 y 23"):
        parse_horas("+15", NOW)
    with pytest.raises(UsageError):
        parse_horas("diez", NOW)
    with pytest.raises(UsageError):
        parse_horas(",", NOW)


def test_parse_parametros() -> None:
    assert parse_parametros([]) == ""
    assert parse_parametros(["a=1,b:2", "url=https://x"]) == "a:1,b:2,url:https://x"
    with pytest.raises(UsageError):
        parse_parametros(["clave con espacio=1"])
    with pytest.raises(UsageError):
        parse_parametros(["solo-clave"])


def test_weekdays_between() -> None:
    assert weekdays_between(date(2026, 10, 16), date(2026, 10, 16)) == ["viernes"]
    assert len(weekdays_between(date(2026, 10, 1), date(2026, 10, 31))) == 7


def test_generate_rejects_bad_range_and_no_users() -> None:
    common = {"canal": "WhatsApp", "hours": [10], "nodo": "N-03-99-10", "app_id": "others-test"}
    with pytest.raises(UsageError):
        generate_rows(["5732"], start=date(2026, 10, 17), end=date(2026, 10, 16), **common)  # type: ignore[arg-type]
    with pytest.raises(UsageError):
        generate_rows([], start=date(2026, 10, 16), end=date(2026, 10, 16), **common)  # type: ignore[arg-type]


def test_render_rejects_delimiter_in_values() -> None:
    rows = generate_rows(
        ["573232540390"],
        canal="WhatsApp",
        start=date(2026, 10, 16),
        end=date(2026, 10, 16),
        hours=[10],
        nodo="N-03-99-10",
        app_id="others;test",
    )
    with pytest.raises(UsageError, match="';'"):
        render_csv(rows)


def test_resolve_csv_path_looks_in_data_dir(tmp_path: Path) -> None:
    # conftest hace chdir a tmp_path: data/ es relativa a la carpeta actual
    (tmp_path / DATA_DIR).mkdir()
    target = tmp_path / DATA_DIR / "mi.csv"
    target.write_text(HEADER + "\n", encoding="utf-8")

    assert resolve_csv_path("mi.csv") == DATA_DIR / "mi.csv"
    assert resolve_csv_path(target) == target
    with pytest.raises(UsageError, match="data/"):
        resolve_csv_path("no-existe.csv")


def test_find_single_csv(tmp_path: Path) -> None:
    data = tmp_path / DATA_DIR
    with pytest.raises(UsageError, match="templates/plantilla.csv"):
        find_single_csv(data)  # la carpeta no existe

    data.mkdir()
    (data / "notas.txt").write_text("x", encoding="utf-8")
    (data / "viejas").mkdir()
    (data / "viejas" / "otra.csv").write_text("x", encoding="utf-8")
    with pytest.raises(UsageError, match="templates/plantilla.csv"):
        find_single_csv(data)  # ni .txt ni subcarpetas cuentan

    (data / "b.csv").write_text("x", encoding="utf-8")
    assert find_single_csv(data) == data / "b.csv"

    (data / "a.csv").write_text("x", encoding="utf-8")
    with pytest.raises(UsageError, match=r"Hay 2 CSV .*\(a\.csv, b\.csv\)"):
        find_single_csv(data)
