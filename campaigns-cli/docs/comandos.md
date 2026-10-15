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

## `dynamo` — [T-006](../backlog/tasks/T-006-dynamo-lectura.md) (solo lectura, permitido en prod)

| Comando | Operación DynamoDB | Notas |
|---|---|---|
| `dynamo get --notification-id ID [--datetime "YYYY-MM-DD HH"]` | `get_item` con `--datetime`; si no, `scan` | Muestra todos los atributos del registro. |
| `dynamo find [--campaign-id] [--user] [--app-id] [-n 200]` | `query` sobre el GSI si existe y se busca por `campaign_id`; si no, `scan` filtrado | Ordena por `datetime` y usuario. |
| `dynamo list [--date YYYY-MM-DD [--hour H] \| --from .. --to ..] [--app-id] [--user] [-n 500]` | Un `query` por partición horaria | Sin argumentos: el día actual (hora Colombia). Máximo 31 días. |
| `dynamo logs [--app-id] [--since 24h \| --from .. --to ..] [--details] [-f] [-n 50]` | Con `--app-id`, `query`; sin él, `scan` filtrado | Tabla de logs del ingester; fechas en **UTC**. `--details` agrega los errores de validación; `-f` sigue las cargas nuevas cada `CLI_POLL_INTERVAL_SECONDS`. |

Todo comando que hace `scan` lo avisa por stderr; si el resultado se corta por `--limit`, también.
Pendiente: `dynamo purge --campaign-id ID` → [T-012](../backlog/tasks/T-012-dynamo-purge.md).

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

## Grupos planeados

| Grupo | Comandos previstos | Tarjeta |
|---|---|---|
| `csv` | `generate`, `validate` (formato `;` de `csv-test.csv`) | [T-004](../backlog/tasks/T-004-csv-generate-validate.md) |
| `s3` | `upload` (valida antes), `ls`, `get`, `rm` | [T-005](../backlog/tasks/T-005-s3-commands.md) |
| `lambda` | `invoke ingester --s3-key`, `invoke scheduler`, `invoke <nombre> --payload`, `--tail`, `--async` | [T-007](../backlog/tasks/T-007-lambda-invoke.md) |
| `dynamo` | `purge --campaign-id` | [T-012](../backlog/tasks/T-012-dynamo-purge.md) |
| `trace` | `run <csv>`: validar → subir → ingesta → IDs → logs del ingester | [T-009](../backlog/tasks/T-009-trace-run.md) |
| `trace` | `--wait-schedule`, `--invoke-scheduler`: scheduler y microservicios | [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md) |
| `trace` | `--verify-delivery`: entrega del mensaje en el fake channel | [T-016](../backlog/tasks/T-016-trace-entrega-canal.md) |
