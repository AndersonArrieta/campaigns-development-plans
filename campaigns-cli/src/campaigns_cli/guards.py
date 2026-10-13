"""Protecciones de entorno: bloqueo en prod y confirmación de operaciones destructivas."""

import typer

from campaigns_cli.errors import UsageError
from campaigns_cli.output import info
from campaigns_cli.settings import Env, Settings
from campaigns_cli.state import AppState


def ensure_not_prod(settings: Settings, action: str) -> None:
    """En prod solo se permiten comandos de lectura."""
    if settings.campaigns_env is Env.PROD:
        raise UsageError(f"'{action}' no está permitido en prod (CAMPAIGNS_ENV=prod).")


def confirm_destructive(state: AppState, message: str) -> None:
    """Pide confirmación salvo `--yes`. Si se rechaza, termina con exit code 0 sin hacer nada."""
    if state.assume_yes:
        return
    if not typer.confirm(message, default=False):
        info("Operación cancelada.")
        raise typer.Exit(code=0)
