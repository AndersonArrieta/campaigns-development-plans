"""Comandos `config`: muestran y validan la configuración cargada."""

import json

import typer
from rich.console import Console
from rich.table import Table

from campaigns_cli.settings import (
    OutputFormat,
    Settings,
    env_var_name,
    is_sensitive,
    mask,
    setting_sources,
)
from campaigns_cli.state import get_state

app = typer.Typer(help="Muestra y valida la configuración del .env.", no_args_is_help=True)

console = Console()

# Variables de recursos que necesitan los comandos que tocan AWS.
REQUIRED_RESOURCES = (
    "campaigns_input_bucket",
    "campaigns_table_name",
    "ingester_lambda_name",
    "scheduler_lambda_name",
    "campaigns_log_groups",
)
OPTIONAL_RESOURCES = ("aws_profile", "campaigns_table_campaign_index")


def _display(name: str, value: object) -> str:
    if value is None:
        return ""
    text = ",".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return mask(text) if is_sensitive(name) and text else text


@app.command()
def show(ctx: typer.Context) -> None:
    """Muestra la configuración efectiva y el origen de cada valor."""
    state = get_state(ctx)
    settings = state.settings
    sources = setting_sources(state.env_file)
    rows = [
        {
            "variable": env_var_name(field),
            "valor": _display(field, getattr(settings, field)),
            "origen": sources[field],
        }
        for field in Settings.model_fields
    ]

    if state.output is OutputFormat.JSON:
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    table = Table(title=f"Configuración ({settings.campaigns_env})")
    table.add_column("Variable", style="cyan")
    table.add_column("Valor")
    table.add_column("Origen", style="dim")
    for row in rows:
        table.add_row(row["variable"], row["valor"], row["origen"])
    console.print(table)


@app.command()
def check(ctx: typer.Context) -> None:
    """Valida que estén configuradas las variables de recursos."""
    state = get_state(ctx)
    settings = state.settings
    rows = []
    for field in (*REQUIRED_RESOURCES, *OPTIONAL_RESOURCES):
        configured = bool(getattr(settings, field))
        required = field in REQUIRED_RESOURCES
        if configured:
            status = "OK"
        elif required:
            status = "FALTA CONFIG"
        else:
            status = "OPCIONAL"
        rows.append(
            {
                "variable": env_var_name(field),
                "obligatoria": required,
                "estado": status,
            }
        )
    missing = [row for row in rows if row["estado"] == "FALTA CONFIG"]

    if state.output is OutputFormat.JSON:
        typer.echo(json.dumps({"ok": not missing, "variables": rows}, indent=2))
    else:
        table = Table(title=f"Chequeo de configuración ({settings.campaigns_env})")
        table.add_column("Variable", style="cyan")
        table.add_column("Obligatoria")
        table.add_column("Estado")
        colors = {"OK": "green", "FALTA CONFIG": "red", "OPCIONAL": "yellow"}
        for row in rows:
            status = str(row["estado"])
            table.add_row(
                str(row["variable"]),
                "sí" if row["obligatoria"] else "no",
                f"[{colors[status]}]{status}[/{colors[status]}]",
            )
        console.print(table)

    if missing:
        raise typer.Exit(code=1)
