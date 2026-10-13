"""Estado compartido entre el callback raíz y los comandos (`ctx.obj`)."""

from dataclasses import dataclass, field
from pathlib import Path

import typer

from campaigns_cli.aws import AwsClients
from campaigns_cli.http import HttpClients
from campaigns_cli.settings import OutputFormat, Settings, load_settings


@dataclass
class AppState:
    env_file: Path | None = None
    output_override: OutputFormat | None = None
    verbose: bool = False
    assume_yes: bool = False
    _settings: Settings | None = field(default=None, repr=False)
    _aws: AwsClients | None = field(default=None, repr=False)
    _http: HttpClients | None = field(default=None, repr=False)

    @property
    def settings(self) -> Settings:
        """Carga perezosa: un `.env` inválido no rompe los comandos que no lo usan."""
        if self._settings is None:
            self._settings = load_settings(self.env_file)
        return self._settings

    @property
    def aws(self) -> AwsClients:
        if self._aws is None:
            self._aws = AwsClients(self.settings)
        return self._aws

    @property
    def http(self) -> HttpClients:
        if self._http is None:
            self._http = HttpClients(self.settings)
        return self._http

    @property
    def output(self) -> OutputFormat:
        return self.output_override or self.settings.cli_output


def get_state(ctx: typer.Context) -> AppState:
    state = ctx.find_object(AppState)
    if state is None:
        state = AppState()
        ctx.obj = state
    return state
