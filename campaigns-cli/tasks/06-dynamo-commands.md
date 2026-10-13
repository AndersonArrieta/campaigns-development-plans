# T-06 — Comandos `dynamo`

- **Grupo:** `dynamo`
- **Secciones del plan:** §2.1, §6, D-4
- **Depende de:** T-03

## Objetivo

Consultar y limpiar la tabla de campañas que llena `ingester_Lambda` y lee `scheduler_Lambda`.

> **Alcance ejecutado (2026-10-13): solo lectura.** Se agregó la **tabla de logs** del ingester para revisar las cargas de campañas (`dynamo logs`, con `--follow`). `dynamo purge` queda pendiente para una task posterior.

## Esquema confirmado

Fuentes: `ingester_Lambda/src/models/notification.py`, `src/controllers/processor.py`, `test/src/libs/test_database_management.py`, `scheduler_Lambda/test/config/config.json`, `docs/docs/ExternalServices.md`, y `Platform_test/.../ValidateCampaignDynamo.java`.

| Tabla | Nombre (`{env}` = dev, qa…) | PK | SK | Atributos |
|---|---|---|---|---|
| Campañas | `nu0284001-artemis-chatbots-platform-{env}-scheduled-campaigns` | `datetime` (`YYYY-MM-DD HH:00:00`, hora Colombia) | `notification_id` | `campaign_id`, `app_id`, `channel`, `user`, `notification_node`, `retries`, `context` (mapa), `expiration_date` (TTL epoch) |
| Logs | `nu0284001-artemis-chatbots-platform-{env}-scheduled-campaigns-logs` | `app_id` (`UNKNOWN` si falla la lectura del archivo) | `datetime` (`str(datetime.now())` de la Lambda, con microsegundos; se asume UTC) | `result`: JSON en texto con `status`, `stats` y `body_result` (de aquí se extraen `campaign_id` y la key del archivo) |

- **D-4 resuelto:** la tabla de campañas **no tiene GSI**. Buscar por `campaign_id` o `user` usa scan (con aviso). `CAMPAIGNS_TABLE_CAMPAIGN_INDEX` se mantiene por si se crea uno.
- Como la PK es la hora programada, `dynamo list` hace **un query por hora** del rango (sin scan), con un máximo de 31 días.

## Contexto de la tabla

Del plan 7938050 (§2.1): la clave es `datetime` + `notification_id`, y cada registro guarda `campaign_id`. Formato de `datetime`: `yyyy-MM-dd HH:mm:ss`.

> ~~Confirmar antes de empezar~~ → confirmado en el código (ver **Esquema confirmado**).

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/dynamo_service.py` | `DynamoService(client, table, campaign_index)` con `get`, `find_by_campaign`, `list_range`, `purge_campaign`. |
| `src/campaigns_cli/commands/dynamo_cmd.py` | Subgrupo `dynamo` con `get`, `find`, `list`, `purge`. |
| `tests/test_dynamo_service.py` | Pruebas con moto (tabla creada con el mismo esquema que dev). |

## Comandos implementados

```text
campaigns dynamo get  --notification-id ID [--datetime "2026-10-13 10"]   # get_item; sin --datetime, scan
campaigns dynamo find [--campaign-id ID] [--user U] [--app-id A] [-n 200]   # scan filtrado (o GSI)
campaigns dynamo list [--date 2026-10-13 [--hour 10] | --from ... --to ...] [--app-id] [--user] [-n 500]
campaigns dynamo logs [--app-id A] [--since 24h | --from ... --to ...] [--details] [-f] [-n 50]
```

- `list` sin argumentos muestra el día actual en hora Colombia.
- `logs` sin `--app-id` hace un scan de la tabla de logs filtrando por fecha (todas las apps); con `--app-id` hace un query.
- `logs --follow` consulta cada `CLI_POLL_INTERVAL_SECONDS` y muestra solo las cargas nuevas, hasta Ctrl+C.
- Todos son de solo lectura y están permitidos en prod.

## Pasos (plan original)

1. Usar el cliente de bajo nivel con `boto3.dynamodb.types.TypeDeserializer` (o el `resource` `Table`) y convertir `Decimal` a `int`/`float` antes de imprimir JSON.
2. `dynamo get --notification-id ID [--datetime DT]`:
   - Con `--datetime` → `get_item` por clave completa.
   - Sin `--datetime` → `scan` con `FilterExpression notification_id = :id`, avisando por stderr que es un scan.
3. `dynamo find --campaign-id ID`:
   - Si hay `CAMPAIGNS_TABLE_CAMPAIGN_INDEX` → `query` sobre el GSI.
   - Si no → `scan` filtrado con advertencia de costo (D-4).
   - Paginar siempre (`LastEvaluatedKey`).
4. `dynamo list --from DT --to DT [--app-id A] [--usuario U]`: rango por `datetime` (query si `datetime` es sort key de alguna clave útil; si es partition key, scan con `BETWEEN`). Columnas: `datetime`, `notification_id`, `campaign_id`, `app_id`, `usuario`, estado.
5. `dynamo purge --campaign-id ID`:
   - `ensure_not_prod` + `confirm_destructive` mostrando cuántos registros se borrarán.
   - Solo borra registros cuyo `app_id == CLI_TEST_APP_ID`; si encuentra otros, los omite y lo reporta.
   - Borrar con `batch_write_item` en lotes de 25, reintentando `UnprocessedItems`.
6. Todos los comandos llaman a `settings.require("campaigns_table_name")`.

## Pruebas

- `get` por clave completa y por scan devuelven el mismo registro.
- `find` con GSI (moto soporta GSI) y sin GSI → mismos resultados; sin GSI se emite la advertencia.
- `find` con más de una página de resultados → devuelve todos.
- `list` filtra correctamente por rango y `app_id`.
- `purge` borra solo los registros de `CLI_TEST_APP_ID` y deja los demás; bloqueado en prod.
- Salida JSON sin `Decimal` (serializable).

## Criterios de terminado

- [x] Esquema real de las tablas documentado en el docstring de `services/dynamo_service.py`.
- [ ] `campaigns dynamo find --campaign-id <id>` devuelve en dev los registros de una campaña cargada. *(pendiente: requiere `.env` de dev con credenciales)*
- [ ] `campaigns dynamo purge` *(pendiente: fuera del alcance de solo lectura)*
- [x] Pruebas (129, cobertura 96 %), ruff y mypy en verde (2026-10-13).
- [ ] Commit (lo hace el desarrollador).
