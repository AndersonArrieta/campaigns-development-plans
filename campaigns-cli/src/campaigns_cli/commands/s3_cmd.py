"""Comandos `s3`: bucket de entrada del ingester (subir dispara la ingesta real)."""

from pathlib import Path
from typing import Annotated

import typer

from campaigns_cli.errors import TestFailedError
from campaigns_cli.guards import confirm_destructive, ensure_not_prod
from campaigns_cli.output import info, render, success, warn
from campaigns_cli.services.csv_service import (
    DATA_DIR,
    Severity,
    resolve_csv_path,
    validate_csv,
)
from campaigns_cli.services.s3_service import S3Service
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import colombia_now

app = typer.Typer(
    help="Bucket de entrada del ingester: subir (dispara la ingesta), listar, descargar y borrar.",
    no_args_is_help=True,
)

YesOption = Annotated[bool, typer.Option("--yes", "-y", help="Omite la confirmación.")]


def _service(state: AppState) -> S3Service:
    settings = state.settings
    settings.require("campaigns_input_bucket")
    return S3Service(
        state.aws.s3, str(settings.campaigns_input_bucket), settings.campaigns_input_prefix
    )


@app.command()
def upload(
    ctx: typer.Context,
    archivo: Annotated[
        str, typer.Argument(help=f"Ruta del CSV (o su nombre dentro de {DATA_DIR}/).")
    ],
    key: Annotated[
        str | None,
        typer.Option("--key", help="Key de destino (por defecto, prefijo + nombre del archivo)."),
    ] = None,
    no_validate: Annotated[
        bool, typer.Option("--no-validate", help="Sube sin validar el CSV.")
    ] = False,
) -> None:
    """Valida y sube un CSV al bucket de entrada: el ingester lo procesa y lo borra."""
    state = get_state(ctx)
    ensure_not_prod(state.settings, "s3 upload")
    path = resolve_csv_path(archivo)
    service = _service(state)

    if no_validate:
        warn("--no-validate: se sube sin validar.")
    else:
        issues = validate_csv(path, colombia_now())
        errors = [issue for issue in issues if issue.severity is Severity.ERROR]
        if errors:
            render(
                [issue.as_dict() for issue in issues], state.output, title=f"Problemas de {path}"
            )
            raise TestFailedError(
                f"{path}: {len(errors)} error(es) de validación; no se subió nada "
                "(revisa con `csv validate` o usa --no-validate)."
            )
        for issue in issues:  # solo quedan avisos
            warn(f"Fila {issue.row}, {issue.column}: {issue.message}")

    result = service.upload(path, key)
    render(result.as_dict(), state.output, title="Archivo subido")
    success(
        f"Subido {path} a s3://{result.bucket}/{result.key}: el ingester lo procesará y lo "
        "borrará del bucket."
    )


@app.command("ls")
def ls(
    ctx: typer.Context,
    prefix: Annotated[
        str | None,
        typer.Option("--prefix", help="Prefijo (por defecto CAMPAIGNS_INPUT_PREFIX)."),
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", min=1, help="Máximo de objetos.")
    ] = None,
) -> None:
    """Lista los objetos del bucket, del más reciente al más antiguo (hora Colombia)."""
    state = get_state(ctx)
    service = _service(state)
    objects, truncated = service.list(prefix, limit)
    render(
        [obj.as_dict() for obj in objects],
        state.output,
        title=f"s3://{service.bucket}/{service.prefix if prefix is None else prefix}",
    )
    if truncated:
        warn(f"Se muestran los {limit} más recientes; usa --limit para ver más.")


@app.command()
def get(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key del objeto.")],
    output_file: Annotated[
        Path | None, typer.Option("-o", "--out", help="Archivo de destino (si no, stdout).")
    ] = None,
) -> None:
    """Descarga un objeto; sin -o imprime su contenido."""
    state = get_state(ctx)
    content = _service(state).download(key)
    if output_file is None:
        typer.echo(content.decode("utf-8-sig", errors="replace"), nl=False)
        return
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(content)
    info(f"Guardado en {output_file} ({len(content)} bytes).")


@app.command()
def rm(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Key del objeto (dentro de CAMPAIGNS_INPUT_PREFIX).")],
    yes: YesOption = False,
) -> None:
    """Borra un objeto del bucket de entrada."""
    state = get_state(ctx)
    settings = state.settings
    ensure_not_prod(settings, "s3 rm")
    service = _service(state)
    if yes:
        state.assume_yes = True
    service.ensure_deletable(key)
    confirm_destructive(state, f"¿Borrar s3://{service.bucket}/{key} en {settings.campaigns_env}?")
    service.delete(key)
    success(f"Borrado s3://{service.bucket}/{key}.")
