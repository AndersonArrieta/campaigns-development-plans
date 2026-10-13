from pathlib import Path
from typing import Annotated

import typer

from campaigns_cli import __version__
from campaigns_cli.commands import config_cmd
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState

app = typer.Typer(
    name="campaigns",
    help="Pruebas sobre los recursos AWS del flujo de campañas.",
    no_args_is_help=True,
)
app.add_typer(config_cmd.app, name="config")


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
    """Pruebas sobre los recursos AWS del flujo de campañas."""
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
