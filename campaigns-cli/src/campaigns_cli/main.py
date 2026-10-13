import typer

from campaigns_cli import __version__

app = typer.Typer(
    name="campaigns",
    help="Pruebas sobre los recursos AWS del flujo de campañas.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Pruebas sobre los recursos AWS del flujo de campañas."""


@app.command()
def version() -> None:
    """Muestra la versión de la CLI."""
    typer.echo(__version__)
