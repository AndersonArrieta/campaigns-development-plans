# T-02 — Settings y carga del `.env`

- **Grupo:** `config`
- **Secciones del plan:** §5, §6
- **Depende de:** T-01

## Objetivo

Cargar toda la configuración de entorno desde un archivo `.env` (o el que indique `--env-file`) con `pydantic-settings`, y exponer los comandos `config show` y `config check` (la parte de AWS de `check` se completa en la T-03).

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/settings.py` | Clase `Settings` y función `load_settings(env_file)`. |
| `src/campaigns_cli/main.py` | Callback raíz con opciones globales `--env-file`, `--output`, `--verbose`, `--yes`; guarda el estado en `ctx.obj`. |
| `src/campaigns_cli/commands/config_cmd.py` | Subgrupo `config` con `show` y `check`. |
| `.env.example` | Todas las variables de §5.1 del plan, con comentarios. |
| `tests/test_settings.py` | Pruebas de carga y validación. |
| `src/campaigns_cli/state.py` | *(agregado al ejecutar)* `AppState` con carga perezosa de `Settings` y `get_state(ctx)`. |
| `tests/conftest.py`, `tests/test_config_cmd.py` | *(agregado al ejecutar)* Aislamiento del `.env` real y pruebas de `config show/check`. |

> **Notas de ejecución:**
> - `Settings` se carga de forma perezosa en `AppState.settings`: un `.env` inválido sale con código 2, pero no rompe comandos que no lo usan (ej. `version`). La traducción global de errores se completa en la T-03.
> - `--output` no tiene alias `-o`, porque `-o` se reserva para archivos de salida (`csv generate -o`, `s3 get -o`).
> - `config check` sale con código 1 si falta alguna variable obligatoria.

## Pasos

1. Definir `Settings`:
   ```python
   from enum import StrEnum
   from pydantic import Field
   from pydantic_settings import BaseSettings, SettingsConfigDict


   class Env(StrEnum):
       DEV = "dev"
       QA = "qa"
       PROD = "prod"


   class Settings(BaseSettings):
       model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

       campaigns_env: Env = Env.DEV
       aws_profile: str | None = None
       aws_region: str = "us-east-1"

       campaigns_input_bucket: str | None = None
       campaigns_input_prefix: str = "campaigns/input/"
       campaigns_table_name: str | None = None
       campaigns_table_campaign_index: str | None = None
       ingester_lambda_name: str | None = None
       scheduler_lambda_name: str | None = None
       campaigns_log_groups: list[str] = Field(default_factory=list)

       cli_output: str = "table"
       cli_wait_timeout_seconds: int = 120
       cli_poll_interval_seconds: int = 5
       cli_test_app_id: str = "others-test"

       def require(self, *fields: str) -> None:
           """Lanza MissingSettingError con la lista de variables vacías que el comando necesita."""
   ```
   - `campaigns_log_groups` se lee como texto separado por comas: usar un `field_validator(mode="before")` que haga `split(",")` y quite espacios y vacíos.
   - Prioridad: variables del proceso > `.env` > defecto (comportamiento nativo de pydantic-settings).
2. `load_settings(env_file: Path | None)`: si `env_file` viene y no existe → error de uso (exit code 2). Si no viene, usar `.env` del directorio actual si existe.
3. Callback raíz en `main.py`: construir un `AppState(settings, output, verbose, assume_yes)` y guardarlo en `ctx.obj`. `--output` sobrescribe `CLI_OUTPUT`.
4. `config show`: tabla clave/valor de la configuración efectiva, indicando el origen (`env`, `.env`, `default`) si es simple de obtener; si no, solo el valor. Enmascarar valores que parezcan secretos (`*KEY*`, `*SECRET*`, `*TOKEN*`).
5. `config check` (versión inicial): reportar qué variables de recursos faltan, sin fallar por las opcionales. La verificación contra AWS se agrega en la T-03.
6. Completar `.env.example` con las variables de §5.1 del plan.

## Pruebas

- `.env` temporal (`tmp_path`) con todas las variables → `Settings` con los valores esperados; `CAMPAIGNS_LOG_GROUPS="a, b,,c"` → `["a", "b", "c"]`.
- Variable del proceso (`monkeypatch.setenv`) prevalece sobre `.env`.
- `CAMPAIGNS_ENV=staging` → error de validación con mensaje claro.
- `--env-file inexistente.env` → exit code 2.
- `settings.require("campaigns_table_name")` con la variable vacía → `MissingSettingError` que nombra `CAMPAIGNS_TABLE_NAME`.
- `config show` con `CliRunner` → muestra `CAMPAIGNS_ENV` y no muestra valores de secretos en claro.

## Criterios de terminado

- [x] No hay nombres de recursos quemados en el código.
- [x] `uv run campaigns config show` funciona aunque falten variables de recursos.
- [x] Pruebas (26), ruff y mypy en verde (2026-10-13).
- [ ] Commit (lo hace el desarrollador).
