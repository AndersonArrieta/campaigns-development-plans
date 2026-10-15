---
id: T-020
aliases: [T-020]
title: "Historial de cargas con reprogramaciones y vaciado de las tablas de campañas y de logs"
status: todo
priority: P1
epic: E-dynamo
estimate: L
depends_on: [T-006, T-012]
type: task
affects: [T-006]
created: 2026-10-15
---

# T-020 — Historial de cargas con reprogramaciones y vaciado de las tablas de campañas y de logs

## Objetivo
Después de subir un CSV, ver con un comando **todo lo que dejó en DynamoDB**: la carga en la
tabla de logs del ingester, las filas que creó en la tabla de campañas y las que agregó después
`platform_campaigns_ms` al reprogramar. Antes de la siguiente prueba, poder **borrar** esos datos
de las dos tablas: **vaciarlas por completo** o borrar solo lo de un CSV.

Amplía [[T-006-dynamo-lectura|T-006]], que es de solo lectura y cuyo `dynamo get` sin `--datetime`
se detiene en la primera fila (`dynamo_service.py:136`, `limit=1`), así que oculta las
reprogramaciones. Reutiliza el borrado por lotes de [[T-012-dynamo-purge|T-012]].

## Cómo se reconocen las reprogramaciones (confirmado en el código)
- **Ingester** (`ingester_Lambda/src/models/notification.py:149-162` y `:185`): una fila por usuario
  y fecha/hora, con un `notification_id` nuevo (`uuid4`) y `retries = "0"`.
- **`platform_campaigns_ms`** (`NotificationDynamoDbAdapter.createItem`, un `PutItem`): escribe una
  fila **nueva** con el **mismo `notification_id`** y otra `datetime`. Conserva `campaign_id`,
  `app_id`, `user`, `channel`, `context` y `notification_node`. Nadie borra la fila anterior:
  el ms no borra y el scheduler tampoco.
  - Fuera de horario (`BatchMessageUseCase.reschedule`): `retries` igual, `datetime` = siguiente
    hora permitida por el cron del `appId`.
  - Reintento `POST /v1/retry` (`RetryUseCase`): `retries + 1`, `datetime` = original
    + `retries_interval_hours`, ajustada al cron.
- Por lo tanto, dentro de un `campaign_id`:
  - un `notification_id` con **una** fila no se reprogramó;
  - un `notification_id` con **varias** filas tiene una historia. La de menor `datetime` es la
    original (el ms siempre mueve la fecha hacia adelante) y las demás son reprogramaciones.
    Se clasifican como `FUERA_DE_HORARIO` si `retries` no cambió y `REINTENTO` si subió.
- Estado de cada fila según la hora Colombia actual: `PENDIENTE` (hora futura), `EN_CURSO`
  (hora actual) o `PASADA`. Que una fila esté `PASADA` no prueba que se haya enviado; el envío se
  confirma con `logs`/`pods`/`channel`.
- La tabla de logs no registra reprogramaciones: solo el ingester escribe en ella.

## Comandos

### Lectura (permitidos en prod)
| Comando | Qué muestra | Acceso |
|---|---|---|
| `dynamo history [--since 24h \| --from .. --to ..] [--app-id]` | Una línea por carga del ingester en la ventana: fecha (UTC), `app_id`, estado, `procesados/exitosos/omitidos/errores`, `campaign_id`, archivo y, de la tabla de campañas, filas totales, `notification_id` distintos, reprogramados y pendientes. | Logs: `query` por `app_id` o `scan` (como `dynamo logs`). Campañas: un `scan` filtrado por `campaign_id IN (...)` (lotes de hasta 100 valores) para todas las cargas de la ventana. |
| `dynamo campaign --campaign-id ID` | Detalle de un CSV: la carga en logs más, por cada `notification_id`, la línea de tiempo `datetime` (hora Colombia) · `retries` · tipo (`ORIGINAL`, `FUERA_DE_HORARIO`, `REINTENTO`) · estado. Resumen al final. | Campañas: GSI si existe, si no `scan`. Logs: `scan` filtrado por `datetime` alrededor de las cargas y `parse_log_entry` para buscar el `campaign_id`. |
| `dynamo get --notification-id ID` (cambio) | Sin `--datetime`, **todas** las filas de ese `notification_id`, ordenadas por `datetime`, con tipo y estado. Con `--datetime` sigue siendo un `get_item`. | `scan` completo (deja de cortar en la primera). |
| `dynamo dump [--table campaigns\|logs\|all] [--app-id] [-n]` | Todas las filas de las tablas, con filtro opcional por `app_id`; pensado para `--output json > evidencias/...`. | `scan` (con aviso); en logs con `--app-id`, `query`. |

### Escritura (bloqueada en prod)
| Comando | Qué borra |
|---|---|
| `dynamo clean [--table campaigns\|logs\|all] [--dry-run]` | **Vacía por completo** las tablas indicadas (por defecto, `all`): todas las filas de todos los `app_id`, incluidas las `UNKNOWN` de logs y las reprogramadas por el ms. |
| `dynamo clean --campaign-id ID [--table ...] [--dry-run]` | Solo lo que dejó ese CSV. En campañas, las filas con ese `campaign_id`, incluidas las reprogramadas, porque el ms lo conserva. En logs, las cargas cuyo `result` trae ese `campaign_id`, incluidas las `UNKNOWN`. |

Las tablas de dev las usa solo el autor de las pruebas, así que vaciarlas no afecta a nadie más.
Por eso el vaciado completo es el comportamiento por defecto (ver ADR-0011).

### Cómo borra
- Antes de borrar, siempre muestra cuántas filas hay por tabla y por `app_id`, y cuántas filas de
  campañas están `PENDIENTE` o `EN_CURSO` (envíos que se perderán).
- Confirmación con `confirm_destructive`, que muestra el entorno y el nombre de cada tabla; `--yes`
  la omite (así `trace run` puede limpiar sin preguntar).
- El borrado es por clave: `scan` paginado con `ProjectionExpression` solo de las claves, y luego
  `batch_write_item`. No se usan `DeleteTable`/`CreateTable`, porque se perderían el TTL, los
  streams y los permisos de la tabla, y la CLI necesitaría permisos de administración.
- Al final hace un `scan` de verificación y reporta cuántas filas quedaron (exit 1 si quedan). Las
  filas que el ingester o el ms escriban durante el borrado pueden quedar.

## Archivos a crear/modificar
- `src/campaigns_cli/services/dynamo_service.py`:
  - `CampaignsTable.by_notification(notification_id)` (todas las filas);
  - `CampaignsTable.by_campaigns(campaign_ids)` (`IN`, en lotes);
  - `LogsTable.all(app_id=None)`.
- `src/campaigns_cli/services/history_service.py` — `NotificationTimeline`, `classify_rows(rows, now)`
  (`ORIGINAL`/`FUERA_DE_HORARIO`/`REINTENTO` y `PENDIENTE`/`EN_CURSO`/`PASADA`),
  `load_history(logs, campaigns, window)`, `campaign_detail(campaign_id)`.
- `src/campaigns_cli/services/clean_service.py` — `plan_clean(tables, campaign_id=None)
  -> CleanPlan`, `execute(plan) -> CleanResult`; usa el borrado por lotes de T-012.
- `src/campaigns_cli/commands/dynamo_cmd.py` — `history`, `campaign`, `dump`, `clean`; `get`
  devuelve todas las filas.
- `tests/test_history_service.py`, `tests/test_clean_service.py`, `tests/test_dynamo_cmd.py`,
  `tests/dynamo_fixtures.py` (filas reprogramadas, de varias apps y `UNKNOWN`).
- `docs/comandos.md`, `docs/recursos-aws.md` (sección "Reprogramaciones"), `docs/configuracion.md`
  (permisos `dynamodb:Scan`, `Query`, `BatchWriteItem`).
- `docs/adr/0011-vaciado-de-tablas-en-dev.md`.

## Tareas
- [ ] `classify_rows` agrupa por `notification_id`, ordena por `datetime` y marca tipo y estado
  (hora Colombia de `timeutils`). `retries` se compara como entero (el ms y el ingester lo guardan
  como texto).
- [ ] `dynamo history`: une cada carga con sus filas usando un solo `scan` de campañas para todos
  los `campaign_id` de la ventana. Las cargas `FAILED` o sin `campaign_id` se muestran sin filas.
  `--details` agrega los errores de validación, como `dynamo logs`.
- [ ] `dynamo campaign`: con `--output table`, una tabla por `notification_id` reprogramado y una
  tabla resumen (usuarios, filas, reprogramados por tipo, pendientes); con `--output json`, la
  estructura completa.
- [ ] `dynamo get` sin `--datetime`: todas las filas; aviso de `scan`.
- [ ] `dynamo dump`: `--table all` emite `{"campaigns": [...], "logs": [...]}` en JSON; en tabla,
  dos tablas.
- [ ] `dynamo clean`:
  1. `ensure_not_prod`; exige las variables de las tablas implicadas.
  2. Arma el plan y muestra cuántas filas se borrarán por tabla y por `app_id` (o por
     `campaign_id`), cuántas son reprogramaciones y cuántas están `PENDIENTE`/`EN_CURSO`. Si alguna está `EN_CURSO`, avisa
     que el scheduler puede estar procesándola.
  3. `--dry-run` termina aquí, con exit 0.
  4. Pide confirmación (`confirm_destructive`); `--yes` la omite.
  5. `batch_write_item` en lotes de 25 con reintento de `UnprocessedItems` (de T-012). Los
     reintentos son seguros porque borrar dos veces la misma clave no tiene efecto.
  6. `scan` de verificación: con vaciado completo, la tabla debe quedar con 0 filas; con
     `--campaign-id`, sin filas de ese `campaign_id`.
  7. Resultado por tabla: borradas, fallidas y restantes; exit 1 si hay fallidas o restantes.
- [ ] Con `--campaign-id`, cada fila se vuelve a comprobar contra ese `campaign_id` justo antes de
  armar el lote, aunque el filtro ya lo haya hecho el `scan`.
- [ ] ADR-0011: las tablas de dev son de uso exclusivo de las pruebas y `dynamo clean` las vacía
  por completo; cambio de la regla `P0` del triage.
- [ ] Actualizar `docs/`.
- [ ] En dev: subir un CSV de `CLI_TEST_APP_ID` con una hora fuera de la ventana del `appId`,
  esperar a que el scheduler y el ms lo reprogramen (o forzarlo con `scheduler run` de
  [[T-019-scheduler-invoke|T-019]]), y guardar en `evidencias/t020/` `history`, `campaign`,
  `clean --campaign-id`, `clean --dry-run` y `clean --yes`.

## Criterios de aceptación
- [ ] `classify_rows` con un `notification_id` de 3 filas (`retries` 0, 0, 1) → `ORIGINAL`,
  `FUERA_DE_HORARIO`, `REINTENTO`, en orden de `datetime`.
- [ ] Con reloj fijo, las filas de la hora actual salen `EN_CURSO`, las futuras `PENDIENTE` y las
  anteriores `PASADA`.
- [ ] `dynamo get --notification-id X` con 2 filas en moto → devuelve las 2 (regresión del
  `limit=1`; el test falla antes del cambio).
- [ ] `dynamo history` con 2 cargas (una `SUCCESSFUL` con reprogramaciones, otra `FAILED`) →
  dos líneas con los conteos correctos, y la de `FAILED` sin filas.
- [ ] `by_campaigns` con 150 `campaign_id` → dos lotes de `IN` y todas las filas encontradas.
- [ ] `dynamo clean --yes` con filas de varias apps, reprogramadas y `UNKNOWN`, y más de 25 por
  tabla → las dos tablas quedan vacías (`scan` con `Count == 0`).
- [ ] `clean --table logs --yes` → vacía solo la tabla de logs; la de campañas no cambia.
- [ ] `clean --campaign-id ID --yes` → borra las filas de ese CSV en las dos tablas, incluidas sus
  reprogramaciones y la fila `UNKNOWN` de logs con ese `ID`; las de otro `campaign_id` siguen ahí.
- [ ] `clean --dry-run` → no llama a `batch_write_item`.
- [ ] Una fila insertada entre el borrado y la verificación final → se informa como restante, exit 1.
- [ ] `UnprocessedItems` simulado → se reintenta hasta borrar.
- [ ] Respuesta "n" a la confirmación → no borra nada (exit 0).
- [ ] `CAMPAIGNS_ENV=prod` → `clean` bloqueado (exit 2); `history`, `campaign`, `dump` y `get`
  permitidos.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_history_service.py tests/test_clean_service.py tests/test_dynamo_cmd.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
# en dev (clean requiere confirmación del usuario: vacía las tablas)
mkdir -p evidencias/t020
uv run campaigns dynamo history --app-id others-test --since 2h 2>&1 | tee evidencias/t020/history.txt
uv run campaigns dynamo campaign --campaign-id <ID> 2>&1 | tee evidencias/t020/campaign.txt
uv run campaigns --yes dynamo clean --campaign-id <ID> 2>&1 | tee evidencias/t020/clean-campaign.txt
uv run campaigns dynamo clean --dry-run 2>&1 | tee evidencias/t020/clean-dry-run.txt
uv run campaigns --yes dynamo clean 2>&1 | tee evidencias/t020/clean.txt
```

## Notas
- **Credenciales de solo lectura:** alcanzan para `history`, `campaign`, `dump` y `get`, pero no
  para `clean`, que necesita `dynamodb:BatchWriteItem` (o `DeleteItem`) sobre las dos tablas.
- La tabla de campañas no guarda fecha de creación: el vínculo "este CSV creó estas filas" es el
  `campaign_id`, que sale de la tabla de logs. Las cargas que fallaron antes de generar el
  `campaign_id` (lectura del archivo) no tienen filas asociadas.
- La tabla de logs guarda `datetime` en UTC y la de campañas en hora Colombia; las salidas lo
  indican en el encabezado de cada columna.
- Sin índice, `campaign` y `clean --campaign-id` hacen `scan` de la tabla de campañas; con un GSI por
  `campaign_id` (`CAMPAIGNS_TABLE_CAMPAIGN_INDEX`), `campaign` pasa a ser un `query`.
