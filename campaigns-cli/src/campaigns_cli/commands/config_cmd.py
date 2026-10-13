"""Comandos `config`: muestran y validan la configuración cargada."""

import typer
from pydantic import SecretStr

from campaigns_cli.errors import TestFailedError
from campaigns_cli.output import render
from campaigns_cli.services.config_service import check_resources, get_identity
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


def _display(name: str, value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
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
    render(rows, state.output, title=f"Configuración ({settings.campaigns_env})")


@app.command()
def check(ctx: typer.Context) -> None:
    """Valida el .env, las credenciales AWS y que existan los recursos configurados."""
    state = get_state(ctx)
    settings = state.settings
    identity = get_identity(state.aws.sts)
    results = check_resources(settings, state.aws, state.http)
    problems = [r for r in results if r.failed]

    rows = [r.as_dict() for r in results]
    title = f"Recursos ({settings.campaigns_env} · cuenta {identity['cuenta']})"
    if state.output is OutputFormat.JSON:
        render({"ok": not problems, "identidad": identity, "recursos": rows}, state.output)
    else:
        render(identity, state.output, title="Identidad AWS")
        render(rows, state.output, title=title)

    if problems:
        raise TestFailedError(f"{len(problems)} recurso(s) con problemas.")
