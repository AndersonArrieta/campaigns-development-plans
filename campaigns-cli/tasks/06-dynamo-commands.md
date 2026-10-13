# T-06 — Comandos `dynamo`

- **Grupo:** `dynamo`
- **Secciones del plan:** §2.1, §6, D-4
- **Depende de:** T-03

## Objetivo

Consultar y limpiar la tabla de campañas que llena `ingester_Lambda` y lee `scheduler_Lambda`.

## Contexto de la tabla

Del plan 7938050 (§2.1): la clave es `datetime` + `notification_id`, y cada registro guarda `campaign_id`. Formato de `datetime`: `yyyy-MM-dd HH:mm:ss`.

> **Confirmar antes de empezar:** cuál es la partition key y cuál la sort key, si existe un GSI por `campaign_id` (D-4) y los nombres exactos de los atributos (`app_id`, `usuario`, estado, etc.). Leerlo con `aws dynamodb describe-table` en dev y ajustar esta task.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/dynamo_service.py` | `DynamoService(client, table, campaign_index)` con `get`, `find_by_campaign`, `list_range`, `purge_campaign`. |
| `src/campaigns_cli/commands/dynamo_cmd.py` | Subgrupo `dynamo` con `get`, `find`, `list`, `purge`. |
| `tests/test_dynamo_service.py` | Pruebas con moto (tabla creada con el mismo esquema que dev). |

## Pasos

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

- [ ] Esquema real de la tabla documentado en el docstring de `DynamoService`.
- [ ] `campaigns dynamo find --campaign-id <id>` devuelve en dev los registros de una campaña cargada.
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
