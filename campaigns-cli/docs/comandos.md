# Referencia de comandos

```
campaigns [--env-file RUTA] [--output table|json] [--verbose|-v] [--yes|-y] <grupo> <acción> [opciones]
```

Las opciones globales van **antes** del grupo. `campaigns <grupo> --help` muestra la ayuda
completa de cada subcomando. Códigos de salida en [arquitectura](arquitectura.md#errores-y-códigos-de-salida).

| Opción global | Efecto |
|---|---|
| `--env-file RUTA` | Usa ese archivo en lugar de `.env`. |
| `--output table\|json` | Formato de salida (sobrescribe `CLI_OUTPUT`). Sin alias `-o`: `-o` se reserva para archivos. |
| `--verbose`, `-v` | Muestra el traceback de los errores. |
| `--yes`, `-y` | Omite las confirmaciones de operaciones destructivas. |

## `version`
Imprime la versión de la CLI. No lee el `.env`.

## `config` — [T-002](../backlog/tasks/T-002-settings-env.md), [T-003](../backlog/tasks/T-003-aws-output-guards.md)

| Comando | Qué hace | AWS |
|---|---|---|
| `config show` | Tabla variable / valor / origen, con secretos enmascarados. | No |
| `config check` | Identidad (`sts get-caller-identity`) y estado de cada recurso: bucket (`head_bucket`), tabla y GSI (`describe_table`), tabla de logs, lambdas (`get_function`) y log groups (`describe_log_groups`). Estados `OK`, `OPCIONAL`, `FALTA CONFIG`, `NO EXISTE`, `SIN PERMISO`, `ERROR`. Sale con 1 si alguno no es `OK`/`OPCIONAL`. | Sí |

## `csv` — [T-004](../backlog/tasks/T-004-csv-generate-validate.md), [T-022](../backlog/tasks/T-022-csv-validate-sin-archivo.md) (sin AWS)

CSV de campaña para `ingester_Lambda`. Los CSV de prueba van en `campaigns-cli/data/`: los dos
comandos buscan ahí el archivo si la ruta indicada no existe, y `generate` escribe ahí por defecto.
`data/` está en el `.gitignore`; la plantilla versionada es `templates/plantilla.csv`.

| Comando | Qué hace |
|---|---|
| `csv validate [archivo]` | Valida con las reglas del ingester. Sin `archivo`, usa el único `*.csv` de `data/` (sin subcarpetas) y muestra cuál; con varios o ninguno sale con 2. Muestra cada problema con fila (la 1 es el encabezado), columna y severidad. Sale con 1 si hay algún `ERROR`; los `AVISO` no cambian el exit code. |
| `csv generate --users U1,U2 --canal C --fecha F --hora H --nodo N [--fecha-fin F] [--app-id A] [--dias D] [--parametros k=v]... [-o archivo]` | Una fila por usuario. `--fecha`/`--fecha-fin` aceptan `dd/mm/aaaa`, `hoy` y `mañana`; `--hora`, horas separadas por coma o `+N` (hora actual de Colombia + N); sin `--dias`, los días de la semana del rango; `--app-id` por defecto `CLI_TEST_APP_ID`. Valida antes de escribir: con errores no escribe nada (exit 2). Sin `-o`, `data/campaign-<AAAAMMDD-HHMMSS>.csv`. |

Reglas (tomadas de `ingester_Lambda/src/libs/source_data_management.py` e `ingester_Conf/ingester.yaml`):

| Columna | Regla |
|---|---|
| Archivo | UTF-8 (con o sin BOM), separador `;`, sin comillas (`QUOTE_NONE`). Deben estar las 9 columnas; el orden y las columnas extra solo dan aviso. Una fila con menos columnas que el encabezado es error (el ingester falla con todo el archivo). |
| `app_id` | No vacío, mínimo 2 caracteres. |
| `canal` | `msteams`, `email`, `sms`, `push` o `whatsapp`, sin distinguir mayúsculas. |
| `usuario` | Teléfono de 11 o 12 dígitos (`^[0-9]{11,12}$`) o email en **minúscula** (`email_eval_regex`), con cualquier canal: el ingester no los cruza. |
| `fecha_inicio`, `fecha_fin` | `dd/mm/aaaa`; `fecha_fin` no anterior a `fecha_inicio` ni a hoy (Colombia). |
| `dias` | Separados por `,`: en español sin tildes (`lunes`…`domingo`) o en inglés (`monday`…). |
| `horas` | Separadas por `,`: enteros 0-23. |
| `nodo` | Empieza por `N-00-00-00` (sin distinguir mayúsculas). |
| `parametros` | Opcional: `clave:valor` separados por `,`, sin espacios en la clave. |

Avisos de lo que el ingester omite sin error: ninguna fecha desde hoy hasta `fecha_fin` cae en
`dias`, o todas las horas son anteriores a la hora en punto actual. En los dos casos no se crea
ninguna fila. Con `--output json`, `validate` devuelve
`{archivo, errores, avisos, problemas: [{fila, columna, severidad, mensaje}]}` y `generate`,
`{archivo, filas, avisos}`.

## `s3` — [T-005](../backlog/tasks/T-005-s3-commands.md), [T-021](../backlog/tasks/T-021-s3-upload-sin-archivo.md) (`upload` y `rm` bloqueados en prod)

Bucket de entrada del ingester (`CAMPAIGNS_INPUT_BUCKET`). **Subir un CSV dispara la ingesta real**,
y el ingester borra el archivo del bucket cuando termina de procesarlo.

| Comando | Qué hace |
|---|---|
| `s3 upload [archivo] [--key KEY] [--no-validate]` | Busca el archivo como `csv validate` (la ruta o su nombre en `data/`). Sin `archivo`, usa el único `*.csv` de `data/` (sin subcarpetas) y muestra cuál; con varios o ninguno sale con 2 sin subir nada. Después lo valida con las mismas reglas y lo sube con `ContentType=text/csv`. Con errores no sube nada y sale con 1; los avisos se muestran y no frenan. Key por defecto: `CAMPAIGNS_INPUT_PREFIX` + nombre del archivo. Muestra bucket, key, `ETag`, `VersionId` y hora de subida (Colombia). |
| `s3 ls [--prefix P] [--limit N]` | Recorre todas las páginas de `list_objects_v2` (por defecto bajo `CAMPAIGNS_INPUT_PREFIX`): key, tamaño y última modificación (Colombia), del más reciente al más antiguo. |
| `s3 get <key> [-o archivo]` | Sin `-o`, imprime el contenido en stdout. |
| `s3 rm <key> [--yes]` | Pide confirmación salvo `--yes`. Con `CAMPAIGNS_INPUT_PREFIX`, solo borra keys dentro del prefijo (fuera: exit 2). Una key inexistente sale con 3. |

- `CAMPAIGNS_INPUT_PREFIX` se normaliza con `/` final (`entrada` → `entrada/`); vacío = raíz del bucket.
- Con `--output json`, `upload` devuelve `{bucket, key, etag, version_id, hora_subida}` y, si la validación
  falla, la lista de problemas; `ls` devuelve `[{key, tamano_bytes, ultima_modificacion}]`.

## `dynamo` — [T-006](../backlog/tasks/T-006-dynamo-lectura.md), [T-012](../backlog/tasks/T-012-dynamo-purge.md), [T-020](../backlog/tasks/T-020-dynamo-historial-y-limpieza.md) (lectura permitida en prod)

| Comando | Operación DynamoDB | Notas |
|---|---|---|
| `dynamo get --notification-id ID [--datetime "YYYY-MM-DD HH"]` | `get_item` con `--datetime`; si no, `scan` completo | Con `--datetime`, todos los atributos del registro. Sin él, **todas** las filas del `notification_id` (la original y sus reprogramaciones) ordenadas por `datetime`, con `tipo` y `estado`; en JSON siempre es una lista. |
| `dynamo find [--campaign-id] [--user] [--app-id] [-n 200]` | `query` sobre el GSI si existe y se busca por `campaign_id`; si no, `scan` filtrado | Ordena por `datetime` y usuario. |
| `dynamo list [--date YYYY-MM-DD [--hour H] \| --from .. --to ..] [--app-id] [--user] [-n N]` | Sin fecha: `scan` de las dos tablas. Con fecha: un `query` por partición horaria | Sin `--date`, `--hour`, `--from` ni `--to` ([T-023](../backlog/tasks/T-023-dynamo-list-todas-las-tablas.md)): **todas** las filas de la tabla de campañas y de la de logs, igual que `dump` (`--user` solo filtra campañas; `-n` es por tabla y sin él no hay límite); en JSON devuelve `{campaigns, logs}`. Con fecha: lo programado en ese rango (hora Colombia), máximo 31 días, `-n` por defecto 500; `--hour` sin `--date` usa hoy. |
| `dynamo logs [--app-id] [--since 24h \| --from .. --to ..] [--details] [-f] [-n 50]` | Con `--app-id`, `query`; sin él, `scan` filtrado | Tabla de logs del ingester; fechas en **UTC**. `--details` agrega los errores de validación; `-f` sigue las cargas nuevas cada `CLI_POLL_INTERVAL_SECONDS`. |

| `dynamo history [--app-id] [--since 24h \| --from .. --to ..] [--details] [-n 50]` | Logs: `query` por `app_id` o `scan`. Campañas: un `scan` con `campaign_id IN (...)` por cada 100 cargas | Una línea por carga: fecha (UTC), `app_id`, estado, conteos del ingester, `campaign_id`, archivo y, de la tabla de campañas, `filas`, `notificaciones`, `reprogramados` y `pendientes`. Las cargas `FAILED` o sin `campaign_id` salen sin filas. |
| `dynamo campaign --campaign-id ID` | Campañas: GSI si existe, si no `scan`. Logs: `scan` con `contains(result, ID)` | Las cargas del CSV (incluida la `UNKNOWN`), una tabla por `notification_id` reprogramado (hora Colombia · `retries` · tipo · estado) y un resumen. En JSON: `{"campaign_id", "cargas", "notificaciones", "resumen"}`. Sale con 1 si no hay nada. |
| `dynamo dump [--table campaigns\|logs\|all] [--app-id] [-n]` | `scan`; en logs con `--app-id`, `query` | Todas las filas, para `--output json > evidencias/...`. En JSON emite `{"campaigns": [...], "logs": [...]}` con las tablas pedidas. |

Todo comando que hace `scan` lo avisa por stderr; si el resultado se corta por `--limit`, también.

**Tipo y estado de cada fila** (ver [recursos AWS § reprogramaciones](recursos-aws.md#reprogramaciones)):
`ORIGINAL`, `FUERA_DE_HORARIO` (mismo `retries` que la fila anterior) o `REINTENTO` (`retries` subió);
`PENDIENTE` (hora futura), `EN_CURSO` (hora actual) o `PASADA`, según la hora Colombia actual.
`PASADA` no prueba que se haya enviado: eso se confirma con `logs`, `pods` o `channel`.

| Comando (escribe, bloqueado en prod) | Operación DynamoDB | Notas |
|---|---|---|
| `dynamo purge --campaign-id ID` | Búsqueda como `find` (GSI o `scan`) y `batch_write_item` en lotes de 25 | Solo borra registros con `app_id == CLI_TEST_APP_ID`; los demás se omiten y se cuentan. Pide confirmación (`--yes` la omite). Reintenta `UnprocessedItems` con espera creciente. Resultado: `borrados`, `omitidos`, `fallidos`; sale con 1 si hay fallidos. No toca la tabla de logs. |
| `dynamo clean [--table campaigns\|logs\|all] [--dry-run]` | `scan` de claves y `batch_write_item` | **Vacía por completo** las tablas indicadas (por defecto las dos): todos los `app_id`, incluidas las cargas `UNKNOWN` y las filas reprogramadas ([ADR-0011](adr/0011-vaciado-de-tablas-en-dev.md)). |
| `dynamo clean --campaign-id ID [--table ...] [--dry-run]` | Campañas: GSI o `scan` filtrado. Logs: `scan` con `contains(result, ID)` | Solo lo de ese CSV: sus filas de campañas (también las reprogramadas, que conservan el `campaign_id`) y sus cargas en logs (también la `UNKNOWN`). Cada fila se vuelve a comprobar contra el `campaign_id` antes de borrarla. |

`dynamo clean`, paso a paso: (1) bloqueado en prod; (2) muestra el plan: filas por tabla y por
`app_id`, cuántas son reprogramaciones y cuántas están `PENDIENTE`/`EN_CURSO` (avisa si hay alguna
`EN_CURSO`, porque el scheduler puede estar procesándola); (3) `--dry-run` termina ahí con exit 0;
(4) pide confirmación con el entorno y el nombre de cada tabla (`--yes` la omite); (5) borra en lotes
de 25 reintentando `UnprocessedItems`; (6) hace un `scan` de verificación; (7) muestra por tabla
`borradas`, `fallidas` y `restantes` y sale con 1 si hay fallidas o restantes (por ejemplo, filas que
el ingester o el ms escribieron durante el borrado). En JSON emite `{"plan": ..., "resultado": [...]}`
(`resultado` es `null` con `--dry-run`).

## `logs` — [T-008](../backlog/tasks/T-008-logs-cloudwatch.md) (solo lectura, hora Colombia)

| Comando | API | Notas |
|---|---|---|
| `logs groups [--prefix /aws/lambda/nu0284001-artemis]` | `describe_log_groups` | Nombre, retención, tamaño y fecha de creación. |
| `logs tail (-l ingester\|scheduler \| -g GRUPO) [--since 15m \| --from .. --to ..] [--filter TEXTO] [-f] [-n 100]` | `filter_log_events` | Orden cronológico; si hay más de `-n` eventos, conserva los más recientes y avisa. `--filter` busca el texto literal. |
| `logs search --id TEXTO [-l ...] [-g ...] [--since 24h \| --from .. --to ..] [-n 200]` | Logs Insights (`start_query` / `get_query_results`) | Texto literal, mínimo 6 caracteres; lotes de 50 log groups; timeout `CLI_WAIT_TIMEOUT_SECONDS` con `stop_query`. Resumen de coincidencias por componente; sale con 1 si no hay ninguna. |

Resolución de log groups en `search`: `--group` > `--lambda` > `CAMPAIGNS_LOG_GROUPS` > log groups
derivados de las lambdas.

Formatos de fecha aceptados en `--from`/`--to`: `YYYY-MM-DD`, `YYYY-MM-DD HH`, `YYYY-MM-DD HH:MM`,
`YYYY-MM-DD HH:MM:SS` (también con `T`). `--since`: número + `s`, `m`, `h` o `d`.

## `channel` — [T-015](../backlog/tasks/T-015-fake-channel-messages.md) (solo lectura, permitido en prod)

Consulta el **fake channel** de la plataforma con un token de Cognito (`client_credentials`),
como el paso "I verify the campaign was delivered successfully" de la prueba E2E de `Platform_test`.

| Comando | Qué hace |
|---|---|
| `channel messages --canal whatsapp\|teams --user ID [-n 50]` | Lista los mensajes recibidos por el usuario (canal, destinatario, texto, tipo). Sin mensajes (404 "No messages found") → "Sin resultados", código 0. |
| `channel verify --canal whatsapp\|teams --user ID --text TEXTO [--attempts 5] [--interval 10]` | Reintenta hasta encontrar un mensaje con ese destinatario, texto y tipo (`text` en WhatsApp, `message` en Teams). Sale con 0 si llegó y con 1 si no, con el último motivo. |

- `--canal` acepta `whatsapp`, `teams` o `msteams` (el valor de la columna `canal` del CSV).
- `--user`: en WhatsApp, el teléfono con indicativo; en Teams, el `recipient.id` (UUID), **no** el
  email que va en el CSV.
- `verify` revisa todos los mensajes del usuario, no solo el primero (la prueba de `Platform_test`
  solo mira el primero).
- El token se pide una vez por ejecución y se reutiliza hasta que vence.
- `config check` incluye las filas "Cognito" (obtiene un token) y "Fake channel" (consulta un
  usuario inexistente y espera 200 o 404 "No messages found").

## `pods` — [T-017](../backlog/tasks/T-017-pods-logs-eks.md), [T-018](../backlog/tasks/T-018-pods-engine-notification-id.md) (solo lectura, permitido en prod)

Logs de los pods de `platform_campaigns_ms` (componente `campaigns`) y `engine_nlp_ms` (componente `engine`) en EKS, sin `kubectl` ni `aws` instalados y sin tocar
`~/.kube/config` ([ADR-0009](adr/0009-acceso-a-kubernetes.md)). Equivale a
`aws eks update-kubeconfig ... && kubectl logs -n <ns> -l <selector> --tail N [-f]`.

| Comando | Qué hace |
|---|---|
| `pods ls [-k campaigns\|engine\|all] [-l SELECTOR]` | Pods de cada componente: estado, contenedores listos, reinicios, creación (hora Colombia), nodo y contenedores. |
| `pods logs [-k ...] [-l SELECTOR] [--pod NOMBRE] [-c CONTENEDOR] [--tail 1000] [--since 1h] [--filter TEXTO] [-C N]` | Últimas líneas de cada pod, mezcladas en orden cronológico con `[componente]`, pod y hora (Colombia). Sale con 1 si no hay pods. |
| `pods logs --notification-id ID [-k ...] [--since 24h] [-C N]` | Busca el id en **campaigns y engine** (últimas 24 h, sin límite de líneas) y resume por componente cuántas coincidencias hubo y entre qué horas. Sale con 1 si no aparece en ninguno. |
| `pods scan ID [-k campaigns -k engine] [--since 24h] [-c CONTENEDOR] [-C N]` | Busca el id **microservicio por microservicio** en el orden de `-k` (por defecto campaigns y luego engine): por cada uno imprime un encabezado, sus líneas en orden cronológico y su resumen antes de pasar al siguiente. Sale con 1 si no aparece en ninguno. |
| `pods logs ... -f [--max-pods 5]` | Sigue todos los pods a la vez (un hilo por pod) hasta Ctrl+C; si la conexión se corta, reconecta desde la última línea sin repetir. Con `--output json`, un objeto JSON por línea. |

- Componentes: `campaigns` → `CAMPAIGNS_POD_SELECTOR` (`app=platform-campaigns-others-v2`) y `engine` →
  `ENGINE_POD_SELECTOR` (`app=platform-engine-nlp-others-campaigns`). Sin `-k`, `campaigns`; con
  `--notification-id`, los dos. `-l` tiene prioridad sobre `-k`.
- `-C N` (`--context`) muestra las N líneas anteriores y posteriores de cada coincidencia en el mismo
  pod, como `grep -C`; las vecinas salen atenuadas (en JSON, `coincide: false`). En el engine el
  `notification_id` va dentro del body JSON y las líneas relacionadas (`Message null Headers`,
  `Sending message to Retry DLQ`) no lo llevan: `-C` las muestra.
- El contenedor por defecto es el principal del pod (no `istio-proxy`).
- `--filter` busca el texto literal; útil con un `notification_id` o `campaign_id`.
- `config check` incluye la fila "EKS": describe el clúster y cuenta los pods de cada componente.
- Con `--output json` y `--notification-id`, la salida es `{"lineas": [...], "resumen": [...]}`.
- Con `--output json`, `pods scan` devuelve una lista con un objeto por componente: `{"componente", "pods",
  "coincidencias", "primera", "ultima", "lineas": [...]}`.

## `scheduler` — [T-019](../backlog/tasks/T-019-scheduler-invoke.md) (bloqueado en prod)

Invoca `scheduler_Lambda` a demanda, sin esperar a la regla de EventBridge de cada hora en punto.
Una invocación = una ejecución: síncrona y sin reintentos que la repitan
([ADR-0010](adr/0010-invocacion-sin-reintentos.md)).

| Comando | Qué hace |
|---|---|
| `scheduler run [--tail] [--yes]` | Vista previa de la partición en curso (`YYYY-MM-DD HH:00:00`, hora Colombia: la única que procesa el scheduler) con filas por `app_id`, confirmación e invocación con `{}`. Muestra `StatusCode`, `FunctionError`, `ExecutedVersion`, `RequestId` y `detail` (`total/successful/failed`). `--tail` muestra los últimos 4 KB del log de la ejecución. |
| `scheduler health [--tail]` | Invoca con `{"type": "health"}`: solo prueba la conexión a Kafka, no despacha ni pide confirmación. Sale con 1 si la función falla o su `statusCode` no es 200. |

- **No es idempotente:** cada `run` vuelve a publicar en Kafka **todas** las filas de la hora en
  curso, incluidas las que EventBridge ya despachó en punto y las de otros equipos. Si hay filas de
  un `app_id` distinto de `CLI_TEST_APP_ID`, la vista previa lo avisa ("se reenviarán notificaciones
  de otros equipos"). Con 0 filas avisa que no se enviará nada y pide confirmación igual.
- Flujo de prueba: CSV con la hora actual → `scheduler run`. Las filas que se agregan después de que
  EventBridge corrió en esa hora solo se despachan así.
- Si la hora cambia entre la vista previa y la invocación (minuto 59), avisa que el scheduler
  procesó la hora siguiente.
- Errores: `TooManyRequestsException` y fallos de conexión antes de enviar se reintentan (máx. 3,
  1-2-4 s). `ReadTimeoutError`, conexión cortada, `ServiceException` o 5xx **no**: el resultado es
  `DESCONOCIDO` (exit 3) y se busca un `Execution result` posterior en el log group del scheduler.
- Exit codes: 0 OK; 1 si hay `FunctionError` o `detail.failed > 0`; 3 si es `DESCONOCIDO`, falta
  `lambda:InvokeFunction` ("las credenciales de solo lectura no pueden invocar la Lambda") u otro
  error de AWS.
- Con `--output json`, `run` devuelve `{partition, partition_at_invoke, preview, invocation:
  {status_code, function_error, executed_version, request_id, attempts, error, payload}, detail,
  outcome, log_tail, execution_results}` y `health` devuelve `{invocation, kafka_ok}`.

## Grupos planeados

| Grupo | Comandos previstos | Tarjeta |
|---|---|---|
| `lambda` | `invoke ingester --s3-key`, `invoke <nombre> --payload`, `--tail` (con el `LambdaService` de `scheduler`, sin `--async`: [ADR-0010](adr/0010-invocacion-sin-reintentos.md)) | [T-007](../backlog/tasks/T-007-lambda-invoke.md) |
| `trace` | `run <csv>`: validar → subir → ingesta → IDs → logs del ingester | [T-009](../backlog/tasks/T-009-trace-run.md) |
| `trace` | `--wait-schedule`, `--invoke-scheduler`: scheduler y microservicios | [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md) |
| `trace` | `--verify-delivery`: entrega del mensaje en el fake channel | [T-016](../backlog/tasks/T-016-trace-entrega-canal.md) |
