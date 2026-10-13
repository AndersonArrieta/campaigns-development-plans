"""Configuración de la CLI cargada desde variables de entorno y archivo `.env`."""

import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from dotenv import dotenv_values
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_ENV_FILE = Path(".env")

SENSITIVE_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD")


class Env(StrEnum):
    DEV = "dev"
    QA = "qa"
    PROD = "prod"


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"


class SettingsError(Exception):
    """El archivo `.env` o las variables de entorno tienen valores inválidos."""


class MissingSettingError(SettingsError):
    """Faltan variables que el comando necesita."""

    def __init__(self, variables: list[str]) -> None:
        self.variables = variables
        super().__init__(f"Falta configurar en el .env: {', '.join(variables)}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Entorno ---
    campaigns_env: Env = Env.DEV
    aws_profile: str | None = None
    aws_region: str = "us-east-1"

    # --- Recursos ---
    campaigns_input_bucket: str | None = None
    campaigns_input_prefix: str = "campaigns/input/"
    campaigns_table_name: str | None = None
    campaigns_table_campaign_index: str | None = None
    ingester_lambda_name: str | None = None
    scheduler_lambda_name: str | None = None

    # --- Logs ---
    campaigns_log_groups: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Comportamiento ---
    cli_output: OutputFormat = OutputFormat.TABLE
    cli_wait_timeout_seconds: int = Field(default=120, gt=0)
    cli_poll_interval_seconds: int = Field(default=5, gt=0)
    cli_test_app_id: str = "others-test"

    @field_validator(
        "aws_profile",
        "campaigns_input_bucket",
        "campaigns_table_name",
        "campaigns_table_campaign_index",
        "ingester_lambda_name",
        "scheduler_lambda_name",
        mode="before",
    )
    @classmethod
    def _empty_as_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("campaigns_log_groups", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def require(self, *fields: str) -> None:
        """Lanza MissingSettingError con las variables vacías que el comando necesita."""
        missing = [env_var_name(name) for name in fields if not getattr(self, name)]
        if missing:
            raise MissingSettingError(missing)


def env_var_name(field: str) -> str:
    return field.upper()


def load_settings(env_file: Path | None = None) -> Settings:
    """Carga Settings. Prioridad: variables del proceso > archivo `.env` > valores por defecto."""
    if env_file is not None and not env_file.is_file():
        raise SettingsError(f"No existe el archivo de configuración: {env_file}")
    try:
        if env_file is None:
            return Settings()
        return Settings(_env_file=env_file)  # type: ignore[call-arg]
    except ValidationError as exc:
        raise SettingsError(_format_validation_error(exc)) from exc


def setting_sources(env_file: Path | None = None) -> dict[str, str]:
    """Indica de dónde sale cada valor: `env`, `.env` o `default`."""
    path = env_file or DEFAULT_ENV_FILE
    file_values = {k.upper() for k in dotenv_values(path)} if path.is_file() else set()
    process_values = {k.upper() for k in os.environ}
    sources: dict[str, str] = {}
    for field in Settings.model_fields:
        name = env_var_name(field)
        if name in process_values:
            sources[field] = "env"
        elif name in file_values:
            sources[field] = path.name
        else:
            sources[field] = "default"
    return sources


def is_sensitive(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in SENSITIVE_MARKERS)


def mask(value: str) -> str:
    return "****" if len(value) <= 4 else f"{value[:2]}****{value[-2:]}"


def _format_validation_error(exc: ValidationError) -> str:
    lines = ["Configuración inválida:"]
    for error in exc.errors():
        name = env_var_name(str(error["loc"][0])) if error["loc"] else "?"
        lines.append(f"  - {name}: {error['msg']} (valor: {error.get('input')!r})")
    return "\n".join(lines)
