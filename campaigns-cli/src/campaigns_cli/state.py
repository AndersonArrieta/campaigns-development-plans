"""Estado compartido entre el callback raíz y los comandos (`ctx.obj`)."""

from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich.console import Console

from campaigns_cli.settings import OutputFormat, Settings, SettingsError, load_settings

err_console = Console(stderr=True)


@dataclass
class AppState:
    env_file: Path | None = None
    output_override: OutputFormat | None = None
    verbose: bool = False
    assume_yes: bool = False
    _settings: Settings | None = field(default=None, repr=False)

    @property
    def settings(self) -> Settings:
        """Carga perezosa: un `.env` inválido no rompe los comandos que no lo usan."""
        if self._settings is None:
            try:
                self._settings = load_settings(self.env_file)
            except SettingsError as exc:
                err_console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=2) from exc
        return self._settings

    @property
    def output(self) -> OutputFormat:
        return self.output_override or self.settings.cli_output


def get_state(ctx: typer.Context) -> AppState:
    state = ctx.find_object(AppState)
    if state is None:
        state = AppState()
        ctx.obj = state
    return state
