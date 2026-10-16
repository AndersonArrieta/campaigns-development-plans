"""Comandos `csv`: generan y validan CSV de campaña para ingester_Lambda (sin AWS)."""

from pathlib import Path
from typing import Annotated

import typer

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.output import info, render, success, warn
from campaigns_cli.services.csv_service import (
    DATA_DIR,
    Severity,
    ValidationIssue,
    default_output,
    find_single_csv,
    generate_rows,
    has_errors,
    parse_fecha,
    parse_horas,
    parse_parametros,
    render_csv,
    resolve_csv_path,
    validate_csv,
    validate_text,
    write_csv,
)
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import colombia_now

app = typer.Typer(
    help=f"Genera y valida CSV de campaña (formato del ingester, separador ';'; en {DATA_DIR}/).",
    no_args_is_help=True,
)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _show_issues(state: AppState, issues: list[ValidationIssue], title: str) -> None:
    if not issues:
        return
    render([issue.as_dict() for issue in issues], state.output, title=title)


@app.command()
def generate(
    ctx: typer.Context,
    users: Annotated[str, typer.Option("--users", help="Usuarios separados por coma.")],
    canal: Annotated[str, typer.Option("--canal", help="WhatsApp, msteams, email, sms o push.")],
    fecha: Annotated[str, typer.Option("--fecha", help="dd/mm/aaaa, 'hoy' o 'mañana'.")],
    hora: Annotated[
        str, typer.Option("--hora", help="Horas 0-23 separadas por coma, o +N (ahora + N).")
    ],
    nodo: Annotated[str, typer.Option("--nodo", help="Nodo N-00-00-00.")],
    fecha_fin: Annotated[
        str | None, typer.Option("--fecha-fin", help="Último día (por defecto, --fecha).")
    ] = None,
    app_id: Annotated[
        str | None, typer.Option("--app-id", help="app_id (por defecto CLI_TEST_APP_ID).")
    ] = None,
    dias: Annotated[
        str | None,
        typer.Option("--dias", help="Días separados por coma (por defecto, los del rango)."),
    ] = None,
    parametros: Annotated[
        list[str] | None,
        typer.Option("--parametros", help="clave=valor (se puede repetir)."),
    ] = None,
    output_file: Annotated[
        Path | None,
        typer.Option(
            "-o", "--out", help=f"Archivo de salida (por defecto {DATA_DIR}/campaign-<fecha>.csv)."
        ),
    ] = None,
) -> None:
    """Genera un CSV de campaña válido para el ingester (una fila por usuario)."""
    state = get_state(ctx)
    now = colombia_now()
    start = parse_fecha(fecha, now.date())
    end = parse_fecha(fecha_fin, now.date()) if fecha_fin else start
    rows = generate_rows(
        _split(users),
        canal=canal,
        start=start,
        end=end,
        hours=parse_horas(hora, now),
        nodo=nodo,
        app_id=app_id or state.settings.cli_test_app_id,
        dias=_split(dias) if dias else None,
        parametros=parse_parametros(parametros or []),
    )

    issues = validate_text(render_csv(rows), now)
    if has_errors(issues):
        _show_issues(state, issues, title="Problemas del CSV a generar")
        raise UsageError("Los valores no pasan la validación del ingester; no se escribió nada.")
    path = write_csv(rows, output_file or default_output(now))

    if state.output is OutputFormat.JSON:
        render(
            {
                "archivo": path,
                "filas": [row.as_dict() for row in rows],
                "avisos": [issue.as_dict() for issue in issues],
            },
            state.output,
        )
    else:
        render([row.as_dict() for row in rows], state.output, title=f"Filas de {path}")
        _show_issues(state, issues, title="Avisos")
    success(f"CSV generado: {path} ({len(rows)} fila(s)).")


@app.command()
def validate(
    ctx: typer.Context,
    archivo: Annotated[
        str | None,
        typer.Argument(
            help=f"Ruta del CSV o su nombre dentro de {DATA_DIR}/. Sin él, el único CSV de "
            f"{DATA_DIR}/."
        ),
    ] = None,
) -> None:
    """Valida un CSV con las reglas del ingester; sale con 1 si hay errores."""
    state = get_state(ctx)
    if archivo is None:
        path = find_single_csv()
        info(f"Archivo: {path}")
    else:
        path = resolve_csv_path(archivo)
    issues = validate_csv(path, colombia_now())
    errors = [issue for issue in issues if issue.severity is Severity.ERROR]
    warnings = [issue for issue in issues if issue.severity is Severity.AVISO]

    if state.output is OutputFormat.JSON:
        render(
            {
                "archivo": path,
                "errores": len(errors),
                "avisos": len(warnings),
                "problemas": [issue.as_dict() for issue in issues],
            },
            state.output,
        )
    else:
        _show_issues(state, issues, title=f"Problemas de {path}")

    if errors:
        raise TestFailedError(f"{path}: {len(errors)} error(es) y {len(warnings)} aviso(s).")
    if warnings:
        warn(f"{path}: sin errores, {len(warnings)} aviso(s).")
    else:
        info(f"{path}: sin problemas.")
