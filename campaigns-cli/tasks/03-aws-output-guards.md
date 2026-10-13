# T-03 — Fábrica AWS, salida y protecciones

- **Grupo:** — (infraestructura común) + completa `config check`
- **Secciones del plan:** §6.1
- **Depende de:** T-02

## Objetivo

Centralizar la creación de clientes boto3, el formato de salida (tabla / JSON), los códigos de salida, el manejo de errores de AWS y las protecciones de entorno, para que los comandos de las tasks siguientes solo tengan que usarlos.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/aws.py` | `AwsClients`: sesión boto3 perezosa y clientes `s3`, `dynamodb`, `lambda_`, `logs`, `sts`. |
| `src/campaigns_cli/output.py` | `render(data, output)`: tabla rich o JSON; helpers `success`, `warn`, `fail`. |
| `src/campaigns_cli/errors.py` | Excepciones de la CLI y `ExitCode`. |
| `src/campaigns_cli/guards.py` | `ensure_not_prod`, `confirm_destructive`. |
| `src/campaigns_cli/main.py` | Envolver la app para traducir excepciones a mensajes y exit codes. |
| `src/campaigns_cli/commands/config_cmd.py` | `config check`: identidad AWS y existencia de recursos. |
| `tests/conftest.py` | Fixtures: `settings` de prueba, `aws_credentials` falsas, `mocked_aws` (moto). |
| `tests/test_guards.py`, `tests/test_output.py`, `tests/test_config_check.py` | Pruebas. |

> **Notas de ejecución (2026-10-13):**
> - **D-3 cambió:** las credenciales AWS van en el `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) como `SecretStr` en `Settings`, con prioridad sobre `AWS_PROFILE`. Los mensajes de error de credenciales apuntan al `.env` en lugar de `aws sso login`.
> - `translate(exc, settings)` en `errors.py` hace la traducción; la aplica `CampaignsGroup.invoke` en `main.py`, así que también funciona con `CliRunner`.
> - La verificación de recursos vive en `services/config_service.py` (sin Typer).
> - Las tablas usan `overflow="fold"`: los IDs y ARNs largos se parten en líneas en lugar de recortarse con "…".
> - Las pruebas de Lambda usan un cliente falso: crear Lambdas en moto exige simular IAM (~7 s por prueba).
> - **Rendimiento:** con el `.venv` dentro de OneDrive (`/mnt/c`) la suite tarda ~220 s; con `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli` (disco Linux) tarda ~5 s.

## Pasos

1. Códigos de salida:
   ```python
   class ExitCode(IntEnum):
       OK = 0
       TEST_FAILED = 1
       USAGE = 2
       AWS = 3
   ```
2. `AwsClients(settings)`: crea `boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)` solo la primera vez que se pide un cliente (para que `csv` y `config show` no requieran credenciales). Configurar `botocore.config.Config(retries={"mode": "standard", "max_attempts": 5})`.
3. Traducción de errores en `main.py` (un `try/except` alrededor de `app()` o un `typer` callback de resultado):
   | Excepción | Mensaje | Exit code |
   |---|---|---|
   | `MissingSettingError` | "Falta `X` en el .env" | 2 |
   | `NoCredentialsError`, `TokenRetrievalError`, `SSOTokenLoadError` | "Sin credenciales. Revisa AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN en el .env" | 3 |
   | `ClientError` `AccessDenied*` | "Permiso denegado para `<operación>` sobre `<recurso>`" | 3 |
   | `ClientError` `ResourceNotFound*`, `NoSuchBucket`, `NoSuchKey` | "No existe `<recurso>`" | 3 |
   | `TestFailedError` | Resumen de la prueba | 1 |
   Con `--verbose` se imprime además el traceback.
4. `output.render`: recibe `list[dict]` o `dict`. En modo `json`, imprime solo JSON válido en stdout (mensajes y spinners van a stderr) para que se pueda encadenar con `jq`.
5. `guards.py`:
   - `ensure_not_prod(settings, action)`: si `campaigns_env == PROD` → `UsageError("'<action>' no está permitido en prod")`.
   - `confirm_destructive(state, message)`: si no hay `--yes`, pide `typer.confirm`; si se rechaza, sale con código 0 sin hacer nada.
6. `config check` completo:
   - `sts.get_caller_identity()` → cuenta y ARN.
   - Para cada recurso configurado: `s3.head_bucket`, `dynamodb.describe_table` (y que exista el GSI si `CAMPAIGNS_TABLE_CAMPAIGN_INDEX` tiene valor), `lambda.get_function`, `logs.describe_log_groups(logGroupNamePrefix=...)`.
   - Tabla con estado `OK` / `FALTA CONFIG` / `NO EXISTE` / `SIN PERMISO` por recurso; exit code 1 si alguno no está `OK`.

## Pruebas

- `ensure_not_prod` con `prod` lanza error; con `dev` no.
- `confirm_destructive` con `--yes` no pregunta; sin `--yes` y respuesta "n" no ejecuta la acción.
- `render` en JSON produce texto que `json.loads` acepta.
- `config check` con moto: bucket y tabla creados → `OK`; bucket sin crear → `NO EXISTE` y exit code 1.
- Error `NoCredentialsError` simulado → exit code 3 y mensaje que apunta a las credenciales del `.env`.

## Criterios de terminado

- [x] Ningún comando crea clientes boto3 por su cuenta: todos usan `AwsClients`.
- [ ] `config check` en dev muestra el estado real de los recursos. *(pendiente: requiere el `.env` de dev con credenciales y nombres reales, D-2)*
- [x] Pruebas (68), ruff y mypy en verde (2026-10-13).
- [ ] Commit (lo hace el desarrollador).
