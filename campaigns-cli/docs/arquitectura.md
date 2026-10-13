# Arquitectura

## Vista general

```
campaigns <grupo> <acción> [opciones]
   │
   ▼
main.py ─────────── CampaignsGroup: callback raíz (--env-file, --output, -v, -y)
   │                 y traducción de excepciones → mensaje + exit code
   ▼
commands/ ───────── config_cmd · dynamo_cmd · logs_cmd · channel_cmd · pods_cmd
   │                 (parsean argumentos, arman servicios, muestran resultados)
   ▼
services/ ───────── config_service · dynamo_service · logs_service · channel_service · k8s_service
   │                 (lógica sin Typer; reciben los clientes boto3 inyectados)
   ▼
state.py ────────── AppState ─┬─ settings.py  (Settings desde .env)
                              ├─ aws.py       (AwsClients: sesión y clientes perezosos)
                              └─ http.py      (HttpClients: clientes httpx; también el de la API de Kubernetes)
   │
   ▼  boto3 / httpx
STS · DynamoDB · CloudWatch Logs · EKS · API de Kubernetes · Cognito · fake channel
(S3 y Lambda: pendientes)

Transversales: output.py · errors.py · guards.py · timeutils.py
```

Regla de capas ([ADR-0002](adr/0002-capas-commands-services.md)): `commands/` solo parsea
argumentos, arma los servicios y muestra resultados; toda la lógica vive en `services/`, que
recibe los clientes boto3 por parámetro y no importa Typer. Así los servicios se prueban con
moto o con clientes falsos.

## Módulos

| Módulo | Responsabilidad |
|---|---|
| `main.py` | App raíz `campaigns`, opciones globales, registro de subgrupos (`app.add_typer`) y `CampaignsGroup.invoke`, que traduce excepciones. |
| `state.py` | `AppState` en `ctx.obj`: `env_file`, `output_override`, `verbose`, `assume_yes`; carga perezosa de `settings` y `aws`. `get_state(ctx)` lo recupera en cada comando. |
| `settings.py` | `Settings` (pydantic-settings), `load_settings`, `setting_sources` (origen de cada valor), enmascarado de secretos y `MissingSettingError`. |
| `http.py` | `HttpClients`: clientes httpx para Cognito y el fake channel (timeouts, verificación SSL configurable). [ADR-0008](adr/0008-cliente-http.md). |
| `aws.py` | `AwsClients`: crea la sesión boto3 la primera vez que se pide un cliente (`s3`, `dynamodb`, `lambda_`, `logs`, `sts`), con reintentos `standard` y 5 intentos. |
| `errors.py` | `ExitCode`, jerarquía `CliError` (`UsageError`, `TestFailedError`, `AwsError`, `ExternalServiceError`, `ServiceAuthError`) y `translate(exc, settings)`. |
| `output.py` | `render` (tabla rich o JSON), `to_json` (serializa `Decimal`, fechas, enums, sets) y mensajes `info/success/warn/fail` a stderr. |
| `guards.py` | `ensure_not_prod` y `confirm_destructive`. |
| `timeutils.py` | Zona de Colombia (UTC-5), `parse_since`, `parse_datetime` y conversiones a epoch ms y al formato de DynamoDB. |
| `services/config_service.py` | Identidad STS y verificación de recursos (`ResourceCheck` con estado). |
| `services/dynamo_service.py` | `CampaignsTable`, `LogsTable`, `parse_log_entry`, `follow_logs`. Esquemas en [recursos AWS](recursos-aws.md). |
| `services/channel_service.py` | `CognitoAuth` (token `client_credentials` reutilizado hasta que vence), `FakeChannel` (`messages`, `wait_for`), `normalize_message`, `parse_channel`. |
| `services/k8s_service.py` | `eks_token` (token de `aws eks get-token`), `EksTokenAuth`, `describe_cluster`, `PodsService` (`list_pods`, `logs`, `stream` con reconexión, `follow_many` con un hilo por pod). [ADR-0009](adr/0009-acceso-a-kubernetes.md). |
| `services/logs_service.py` | `LogsService`: Logs Insights (`search`), `filter_log_events` (`events`, `follow`) y `list_groups`. |

## Ciclo de una invocación

1. Typer parsea las opciones globales y el callback raíz guarda un `AppState` en `ctx.obj`.
   Todavía no se lee el `.env` ni se crea ninguna sesión AWS.
2. El comando llama a `get_state(ctx)`. Al acceder a `state.settings` se carga el `.env`
   (un `.env` inválido sale con código 2, pero `campaigns version` sigue funcionando).
3. El comando exige solo lo que necesita con `settings.require("campaigns_table_name", ...)`.
4. Al acceder a `state.aws.<cliente>` se crea la sesión boto3 ([configuración § credenciales](configuracion.md#credenciales-aws)).
5. El servicio hace las llamadas y devuelve dataclasses o dicts; el comando los pasa a `render`.
6. Si algo lanza una excepción, `CampaignsGroup.invoke` la traduce (ver abajo) y sale con su
   código; con `--verbose` imprime además el traceback.

## Errores y códigos de salida

| Código | Significado | Origen típico |
|---|---|---|
| `0` | OK | — |
| `1` | Prueba fallida | `TestFailedError`: `config check` con recursos en problema, `logs search` sin coincidencias, consulta de Logs Insights que no termina. |
| `2` | Uso o configuración | `UsageError`, `SettingsError`, `MissingSettingError`, opciones inválidas. |
| `3` | AWS o servicio externo | Credenciales ausentes o vencidas, permisos, recurso inexistente, conexión; Cognito o fake channel rechazan o no responden. |

`translate` reconoce:

| Excepción | Mensaje |
|---|---|
| `NoCredentialsError`, `PartialCredentialsError`, errores de token SSO | "Sin credenciales AWS válidas" + pista (`.env` o perfil). |
| `ClientError` `ExpiredToken*`, `InvalidClientTokenId`, `UnrecognizedClientException` | "Credenciales AWS vencidas o inválidas". |
| `ClientError` `AccessDenied*`, `UnauthorizedOperation`, `403` | "Permiso denegado en `<operación>`". |
| `ClientError` `ResourceNotFoundException`, `NoSuchBucket`, `NoSuchKey`, `404` | "No existe el recurso solicitado en `<operación>`". |
| `ProfileNotFound`, `NoRegionError`, `EndpointConnectionError`, otros `BotoCoreError` | Mensaje específico, código 3. |
| `httpx.TimeoutException` / `httpx.TransportError` | "El servicio no respondió a tiempo" / "No se pudo conectar con `<url>`", código 3. |
| `ExternalServiceError`, `ServiceAuthError` (Cognito, fake channel) | Mensaje del servicio (sin el secreto), código 3. |

Una excepción no reconocida se propaga con su traceback (es un bug).

## Salida

- `--output table|json` (opción global, antes del grupo) sobrescribe `CLI_OUTPUT`.
- **Datos a stdout, mensajes a stderr.** En JSON, stdout contiene solo JSON válido, apto para `jq`.
- Las tablas usan `overflow="fold"`: IDs y ARNs largos se parten en líneas en vez de recortarse.
- Estados con color: `OK` verde; `OPCIONAL`/`OMITIDA` amarillo; `FALTA CONFIG`, `NO EXISTE`,
  `SIN PERMISO`, `ERROR`, `FALLA` rojo.

## Protecciones

- `ensure_not_prod(settings, acción)`: con `CAMPAIGNS_ENV=prod` lanza `UsageError`. Todo
  comando que escriba (subir a S3, invocar lambdas, borrar) debe llamarlo. Los de lectura
  (`config`, `dynamo get/find/list/logs`, `logs *`, `channel *`, `pods *`, `s3 ls`) están permitidos en prod.
- `confirm_destructive(state, mensaje)`: pide confirmación salvo `--yes`; si se rechaza, sale
  con código 0 sin hacer nada.
- `dynamo purge` ([T-012](../backlog/tasks/T-012-dynamo-purge.md)) solo borrará registros con
  `app_id == CLI_TEST_APP_ID`.

## Fechas y zonas horarias

| Fuente | Zona | Cómo lo maneja la CLI |
|---|---|---|
| Tabla de campañas (`datetime`) | Hora Colombia, sin zona | Se consulta y muestra tal cual (`colombia_now`). |
| Tabla de logs (`datetime`) | UTC (`datetime.now()` en la Lambda) | `dynamo logs --since/--from/--to` en UTC. |
| CloudWatch Logs | epoch ms | Entrada y salida en hora Colombia (`colombia_to_epoch_ms`, `epoch_ms_to_colombia`). |
| Logs Insights `@timestamp` | UTC | Se convierte a hora Colombia. |

Ver [ADR-0006](adr/0006-hora-colombia.md).
