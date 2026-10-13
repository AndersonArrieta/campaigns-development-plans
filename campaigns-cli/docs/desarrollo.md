# Desarrollo

## Entorno

```bash
source ~/.local/bin/env                                   # uv en el PATH
export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli  # .venv fuera de OneDrive
uv sync                                                   # instala según uv.lock
uv run campaigns --help
uv tool install --editable .                              # opcional: `campaigns` en el PATH
```

- Python ≥ 3.12 (`.python-version`), build backend `uv_build`, entry point
  `campaigns = "campaigns_cli.main:app"`.
- **WSL + OneDrive:** con el `.venv` dentro de `/mnt/c` la suite tarda ~220 s; en el disco Linux, ~30 s o menos.
- Dependencias: `typer`, `rich`, `boto3`, `pydantic-settings`, `httpx`. Dev: `pytest`, `pytest-cov`,
  `moto[dynamodb,logs,s3]`, `ruff`, `mypy`, `boto3-stubs[dynamodb,lambda,logs,s3,sts]`.

## Comandos de calidad

Desde `campaigns-cli/`; los tres deben quedar en verde en cada cambio:

```bash
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

- ruff: línea de 100, `py312`, reglas `E F I B UP SIM`.
- mypy en modo estricto sobre `campaigns_cli` (con los stubs de boto3 solo bajo `TYPE_CHECKING`).

## Pruebas

| Archivo | Qué cubre | Técnica |
|---|---|---|
| `tests/conftest.py` | Aislamiento | Fixture `autouse` `isolated_env`: borra las variables de `Settings` y de AWS, apunta `~/.aws` a rutas inexistentes y cambia al `tmp_path`, para que nunca se lea el `.env` real. Fixtures `write_env`, `aws_credentials`, `mocked_aws`. |
| `test_settings.py`, `test_config_cmd.py` | Carga del `.env`, prioridad, validación, `config show` | `CliRunner` |
| `test_aws.py`, `test_errors.py`, `test_guards.py`, `test_output.py` | Sesión, traducción de errores, protecciones, salida | unitarias |
| `test_config_check.py` | `config check` | moto + cliente Lambda falso |
| `test_dynamo_service.py`, `test_dynamo_cmd.py` (`dynamo_fixtures.py`) | Tablas con el mismo esquema que dev | moto |
| `test_logs_service.py`, `test_logs_cmd.py` | Logs Insights, `filter_log_events` | `botocore.stub.Stubber` / clientes falsos |
| `test_channel_service.py`, `test_channel_cmd.py` (`channel_fixtures.py`) | Cognito y fake channel | `httpx.MockTransport` con un servidor falso (`FakeServer`) |
| `test_timeutils.py`, `test_cli.py` | Fechas; humo de la app | unitarias |

Reglas:
- **Nunca AWS ni HTTP real en la suite.** moto para S3, DynamoDB y STS; `Stubber` o clientes falsos
  donde moto no alcanza (invocar Lambdas exige Docker; Logs Insights tiene soporte limitado).
- Los servicios aceptan `sleep` y `clock` inyectables para probar polling y timeouts sin esperar.
- Cobertura actual: 97 % (213 pruebas). El umbral de 80 % se fijará en CI ([T-014](../backlog/tasks/T-014-ci-github-actions.md)).

## Cómo agregar un grupo de comandos

1. `src/campaigns_cli/services/<grupo>_service.py`: clases o funciones que reciben el cliente
   boto3 (`state.aws.<cliente>`) y devuelven dataclasses o dicts. Sin Typer.
2. `src/campaigns_cli/commands/<grupo>_cmd.py`: `app = typer.Typer(help=..., no_args_is_help=True)`;
   cada comando hace `state = get_state(ctx)`, `state.settings.require(...)`, llama al servicio y
   usa `render(..., state.output)`. Mensajes con `info/warn/success` (stderr).
3. Si el comando escribe: `ensure_not_prod(settings, "<grupo> <acción>")`; si borra, además
   `confirm_destructive(state, "...")`.
4. Errores esperados: `UsageError` (2), `TestFailedError` (1); los de boto3 se dejan propagar
   y los traduce `errors.translate`.
5. Registrar en `main.py`: `app.add_typer(<grupo>_cmd.app, name="<grupo>")`.
6. Pruebas del servicio (moto/Stubber) y del comando (`CliRunner`); actualizar
   [comandos](comandos.md), [configuración](configuracion.md) si hay variables nuevas, y el README.

## Convenciones

- Mensajes, ayudas, docstrings y comentarios en español.
- Horas mostradas en hora Colombia ([ADR-0006](adr/0006-hora-colombia.md)).
- Ningún nombre de recurso quemado: todo desde `Settings`.
- Secretos: `.env` y `.env.*` en `.gitignore`; `.env.example` sin valores de credenciales.

## Flujo de trabajo con el backlog

El trabajo pendiente vive en [`backlog/`](../backlog/README.md):

- La [ready queue](../backlog/dashboards/ready-queue.md) indica qué tarjeta sigue.
- Una tarjeta se ejecuta con [`_prompts/execute-task.md`](../backlog/_prompts/execute-task.md)
  como mensaje de sistema y su id como mensaje de usuario.
- Commit por tarjeta: `feat(campaigns-cli): [T-0NN] <resumen>` o `fix(campaigns-cli): [B-0NN] <resumen>`.
- Si el cambio altera cómo funciona la CLI, se actualiza esta carpeta `docs/` en la misma tarjeta.
- Si toma o cambia una decisión de arquitectura, se escribe un ADR en [`docs/adr/`](adr/README.md).
