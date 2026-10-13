# T-08 — Comandos `logs`

- **Grupo:** `logs`
- **Secciones del plan:** §2.1, §6
- **Depende de:** T-03

## Objetivo

Buscar un identificador (`notification_id`, `campaign_id` u otro texto) en los log groups de todos los componentes del flujo con CloudWatch Logs Insights, y mostrar en qué componente aparece y cuándo.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/logs_service.py` | `LogsService(client)` con `search(groups, term, start, end, limit) -> list[LogHit]`. |
| `src/campaigns_cli/commands/logs_cmd.py` | Subgrupo `logs` con `search`. |
| `src/campaigns_cli/timeutils.py` | `parse_since("15m" / "2h" / "1d" / ISO) -> datetime`. |
| `tests/test_logs_service.py` | Pruebas con `Stubber`. |

## Pasos

1. Firma:
   ```text
   campaigns logs search --id <texto> [--since 1h | --from ISO --to ISO] \
       [--group /aws/lambda/ingester ...] [--limit 200]
   ```
   - Sin `--group`, usa `CAMPAIGNS_LOG_GROUPS`.
2. Consulta Logs Insights:
   ```text
   fields @timestamp, @log, @logStream, @message
   | filter @message like /<id escapado>/
   | sort @timestamp asc
   | limit <limit>
   ```
   - Escapar el término para regex (`re.escape`) y rechazar términos de menos de 6 caracteres (evita consultas costosas).
   - `start_query` acepta hasta 50 log groups por consulta; partir en lotes si hay más.
   - Esperar con `get_query_results` cada `CLI_POLL_INTERVAL_SECONDS` hasta `Complete` / `Failed` / `Cancelled` / `Timeout`, con tope `CLI_WAIT_TIMEOUT_SECONDS`; si se agota, `stop_query` y avisar.
3. Salida:
   - Tabla: hora, componente (nombre corto derivado del log group), log stream, mensaje recortado a una línea.
   - Resumen al final: cantidad de coincidencias por log group, marcando con ✗ los grupos sin coincidencias.
   - JSON: lista completa de `LogHit` + resumen.
4. Permitido en prod (solo lectura).

## Pruebas

- Con `Stubber`: `start_query` recibe la consulta y los grupos esperados; `get_query_results` `Running` → `Complete` → devuelve los hits parseados.
- `--since 2h` → `startTime` correcto (epoch en segundos).
- Más de 50 grupos → dos llamadas a `start_query`.
- Consulta que no termina antes del timeout → se llama `stop_query` y exit code 1.
- Término corto → error de uso.

> El soporte de moto para Logs Insights es limitado; usar `Stubber` para estas pruebas.

## Criterios de terminado

- [ ] `campaigns logs search --id <notification_id> --since 1h` en dev muestra las trazas del ingester y del scheduler para un envío real.
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
