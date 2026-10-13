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

## Grupos planeados

| Grupo | Comandos previstos | Tarjeta |
|---|---|---|
| `csv` | `generate`, `validate` (formato `;` de `csv-test.csv`) | [T-004](../backlog/tasks/T-004-csv-generate-validate.md) |
| `s3` | `upload` (valida antes), `ls`, `get`, `rm` | [T-005](../backlog/tasks/T-005-s3-commands.md) |
| `lambda` | `invoke ingester --s3-key`, `invoke scheduler`, `invoke <nombre> --payload`, `--tail`, `--async` | [T-007](../backlog/tasks/T-007-lambda-invoke.md) |
| `dynamo` | `purge --campaign-id` | [T-012](../backlog/tasks/T-012-dynamo-purge.md) |
| `trace` | `run <csv>`: validar → subir → ingesta → IDs → logs del ingester | [T-009](../backlog/tasks/T-009-trace-run.md) |
| `trace` | `--wait-schedule`, `--invoke-scheduler`: scheduler y microservicios | [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md) |
