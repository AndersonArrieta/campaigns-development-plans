# Configuración

Toda la configuración sale de variables de entorno, normalmente desde un archivo `.env` en la
carpeta desde la que se ejecuta la CLI. La plantilla versionada es
[`.env.example`](../.env.example); el `.env` real no se versiona.

## Carga

- **Prioridad:** variables del proceso > archivo `.env` > valores por defecto.
- **Otro archivo:** `campaigns --env-file .env.qa <grupo> ...`. Si el archivo no existe, sale con código 2.
- **Validación perezosa:** el `.env` se lee la primera vez que un comando pide `settings`; las
  variables de recursos se exigen solo en el comando que las usa (`settings.require(...)`), así
  que `config show` funciona aunque falten.
- **Valores vacíos** cuentan como no configurados.
- `campaigns config show` muestra el valor efectivo y su origen (`env`, `.env` o `default`),
  con los secretos enmascarados (`AK****YZ`).

## Variables

| Variable | Tipo / defecto | Uso | La exige |
|---|---|---|---|
| `CAMPAIGNS_ENV` | `dev` \| `qa` \| `prod` · `dev` | Ambiente; `prod` bloquea los comandos que escriben. | — |
| `AWS_REGION` | texto · `us-east-1` | Región de la sesión. | — |
| `AWS_ACCESS_KEY_ID` | secreto | Credencial estática. Va junto con la siguiente. | — |
| `AWS_SECRET_ACCESS_KEY` | secreto | Credencial estática. | — |
| `AWS_SESSION_TOKEN` | secreto | Solo para credenciales temporales (`ASIA...`). | — |
| `AWS_PROFILE` | texto | Alternativa: perfil de `~/.aws/config` (o SSO). | — |
| `CAMPAIGNS_INPUT_BUCKET` | texto | Bucket de entrada del ingester. | `s3`, `trace` |
| `CAMPAIGNS_INPUT_PREFIX` | texto · vacío | Prefijo de las keys (vacío = raíz del bucket). | `s3` |
| `CAMPAIGNS_TABLE_NAME` | texto | Tabla de campañas. | `dynamo get/find/list` |
| `CAMPAIGNS_TABLE_CAMPAIGN_INDEX` | texto · vacío | GSI por `campaign_id`; vacío = scan ([ADR-0004](adr/0004-busquedas-sin-gsi.md)). | — |
| `CAMPAIGNS_LOGS_TABLE_NAME` | texto | Tabla de logs del ingester. | `dynamo logs` |
| `INGESTER_LAMBDA_NAME` | texto | Nombre de `ingester_Lambda`; de él se deriva su log group. | `logs -l ingester`, `lambda` |
| `SCHEDULER_LAMBDA_NAME` | texto | Nombre de `scheduler_Lambda`. | `logs -l scheduler`, `lambda` |
| `COGNITO_TOKEN_URL` | texto | Dominio de Cognito; se agrega `/oauth2/token` si falta. | `channel` |
| `COGNITO_CLIENT_ID` | texto | Cliente OAuth2 (`client_credentials`). | `channel` |
| `COGNITO_CLIENT_SECRET` | secreto | Secreto del cliente; enmascarado en `config show`, nunca en mensajes. | `channel` |
| `FAKE_CHANNEL_BASE_URL` | texto | Base del fake channel (`…/artemis/platform/fake-channel/v1`). | `channel` |
| `FAKE_CHANNEL_VERIFY_SSL` | booleano · `true` | `false` desactiva la verificación del certificado del fake channel ([ADR-0008](adr/0008-cliente-http.md)). | — |
| `CAMPAIGNS_LOG_GROUPS` | lista separada por comas | Log groups de `logs search`. Vacío = `/aws/lambda/<INGESTER>` y `/aws/lambda/<SCHEDULER>`. | `logs search` (si no se pasa `-g`/`-l`) |
| `CLI_OUTPUT` | `table` \| `json` · `table` | Formato de salida por defecto (`--output` lo sobrescribe). | — |
| `CLI_WAIT_TIMEOUT_SECONDS` | entero > 0 · `120` | Tope de espera (Logs Insights, `trace`). | — |
| `CLI_POLL_INTERVAL_SECONDS` | entero > 0 · `5` | Intervalo de polling (`--follow`, Logs Insights). | — |
| `CLI_TEST_APP_ID` | texto · `others-test` | `app_id` de los datos de prueba; lo único que `purge` puede borrar. | `csv`, `dynamo purge` |

## Credenciales AWS

`AwsClients` crea la sesión así ([ADR-0003](adr/0003-credenciales-en-env.md)):

1. Si hay `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` (y opcionalmente `AWS_SESSION_TOKEN`), se usan esas.
2. Si no, `AWS_PROFILE` (si está) o la cadena estándar de boto3.

Reglas de validación: las dos llaves van juntas y `AWS_SESSION_TOKEN` exige ambas; si no, la
CLI no arranca (código 2). Las credenciales son `SecretStr`: no aparecen en `repr`, tracebacks
ni mensajes de validación. Las temporales vencen en pocas horas; el error lo indica y sale con 3.

## Nombres de recursos por ambiente

Patrones tomados de `Platform_test` e `ingester_Lambda` (`{env}` = `dev`, `qa`…):

| Recurso | Nombre |
|---|---|
| Bucket de entrada | `nu0284001-artemis-chatbots-platform-{env}-campaigns-data` (el CSV va en la raíz) |
| Tabla de campañas | `nu0284001-artemis-chatbots-platform-{env}-scheduled-campaigns` |
| Tabla de logs | `nu0284001-artemis-chatbots-platform-{env}-scheduled-campaigns-logs` |
| Ingester | `nu0284001-artemis-plc-{env}-campaigns-ingester-lambda` |
| Scheduler | `nu0284001-artemis-plc-{env}-campaigns-scheduler-lambda` |
| Log groups de las lambdas | `/aws/lambda/<nombre de la lambda>` |
| Cognito (token) | `https://chatbots-artemis-{env}.auth.us-east-1.amazoncognito.com` |
| Fake channel | `https://informacion-ext-{env}.apps.ambientesbc.com/artemis/platform/fake-channel/v1` |
| Log groups de `platform_campaigns_ms` y `engine_nlp_ms` | **Sin confirmar.** Se descubren en [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md); mientras tanto, `--group` o `CAMPAIGNS_LOG_GROUPS`. |

## Credenciales del fake channel

`COGNITO_CLIENT_ID` y `COGNITO_CLIENT_SECRET` son los de la prueba E2E de `Platform_test`
(propiedades `-DclientId` y `-DclientSecret` de su pipeline). Van solo en el `.env` local. Las cuatro
variables `COGNITO_*`/`FAKE_CHANNEL_BASE_URL` son opcionales en conjunto: sin ninguna, `config check`
muestra Cognito y fake channel como `OPCIONAL`; con algunas, `FALTA CONFIG`.

## Permisos IAM

| Grupo | Acciones |
|---|---|
| `config check` | `sts:GetCallerIdentity`, `s3:ListBucket` (para `HeadBucket`), `dynamodb:DescribeTable`, `lambda:GetFunction`, `logs:DescribeLogGroups` |
| `dynamo` (lectura) | `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan` sobre las dos tablas |
| `logs` | `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:StartQuery`, `logs:GetQueryResults`, `logs:StopQuery` |
| `dynamo purge` (pendiente) | `dynamodb:BatchWriteItem` sobre la tabla de campañas |
| `s3` (pendiente) | `s3:PutObject`, `s3:ListBucket`, `s3:GetObject`, `s3:DeleteObject` |
| `lambda` (pendiente) | `lambda:InvokeFunction` (+ `s3:GetObject` para el `head_object` del ingester) |

En `config check`, un recurso sin permiso sale como `SIN PERMISO` en lugar de fallar todo el comando.
