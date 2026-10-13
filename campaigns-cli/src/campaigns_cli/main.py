from pathlib import Path
from typing import Annotated, Any

import typer
from typer.core import TyperGroup

from campaigns_cli import __version__
from campaigns_cli.commands import channel_cmd, config_cmd, dynamo_cmd, logs_cmd
from campaigns_cli.errors import translate
from campaigns_cli.output import err_console, fail
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState


class CampaignsGroup(TyperGroup):
    """Grupo raíz: traduce las excepciones conocidas a un mensaje corto y su exit code."""

    def invoke(self, ctx: typer.Context) -> Any:  # type: ignore[override]
        try:
            return super().invoke(ctx)
        except Exception as exc:
            state = ctx.obj if isinstance(ctx.obj, AppState) else AppState()
            translated = translate(exc, state._settings)
            if translated is None:
                raise
            message, exit_code = translated
            fail(message)
            if state.verbose:
                err_console.print_exception()
            raise typer.Exit(code=exit_code) from exc


app = typer.Typer(
    name="campaigns",
    help="Pruebas sobre los recursos AWS del flujo de campañas.",
    no_args_is_help=True,
    cls=CampaignsGroup,
)
app.add_typer(config_cmd.app, name="config")
app.add_typer(dynamo_cmd.app, name="dynamo")
app.add_typer(logs_cmd.app, name="logs")
app.add_typer(channel_cmd.app, name="channel")


@app.callback()
def main(
    ctx: typer.Context,
    env_file: Annotated[
        Path | None,
        typer.Option(
            "--env-file",
            help="Archivo de configuración a usar en lugar de .env.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    output: Annotated[
        OutputFormat | None,
        typer.Option("--output", help="Formato de salida (sobrescribe CLI_OUTPUT)."),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Muestra detalles de errores.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Omite las confirmaciones.")] = False,
) -> None:
    """Pruebas sobre los recursos AWS del flujo de campañas.

    Códigos de salida: 0 OK, 1 prueba fallida, 2 uso/configuración, 3 AWS o servicio externo.
    """
    ctx.obj = AppState(
        env_file=env_file,
        output_override=output,
        verbose=verbose,
        assume_yes=yes,
    )


@app.command()
def version() -> None:
    """Muestra la versión de la CLI."""
    typer.echo(__version__)
