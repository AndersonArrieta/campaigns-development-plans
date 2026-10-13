# T-09 — Prueba de punta a punta `trace run`

- **Grupo:** `trace`
- **Secciones del plan:** §2.1, §6, §11 (criterio 4)
- **Depende de:** T-04, T-05, T-06, T-07, T-08

## Objetivo

Encadenar los servicios de las tasks anteriores en una sola prueba que suba un CSV, confirme que el ingester creó los registros en DynamoDB y verifique en qué componentes aparecen sus `notification_id` y `campaign_id` en los logs, con un reporte OK/FALLA por etapa.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/trace_service.py` | `TraceService(csv, s3, dynamo, logs, settings)` con `run(path, options) -> TraceReport`. |
| `src/campaigns_cli/commands/trace_cmd.py` | Subgrupo `trace` con `run`. |
| `tests/test_trace_service.py` | Pruebas con los servicios simulados (fakes), sin AWS. |

## Etapas

| # | Etapa | Cómo se verifica | Falla si |
|---|---|---|---|
| 1 | Validar CSV | `csv_service.validate_csv` | Hay errores de formato. |
| 2 | Subir a S3 | `s3_service.upload`; se guarda la hora de subida `t0` | Error de S3. |
| 3 | Ingesta | Polling de `dynamo_service.list_range` filtrando por `app_id` y los `usuario` del CSV, con registros creados después de `t0` | No aparecen todos los registros esperados antes del timeout. |
| 4 | Identificadores | Se extraen `campaign_id` (debe ser uno solo para el archivo) y los `notification_id` | Más de un `campaign_id` o faltan `notification_id`. |
| 5 | Logs del ingester | `logs_service.search` por `campaign_id` en el log group del ingester | Sin coincidencias. |
| 6 | Logs aguas abajo (opcional, `--wait-schedule`) | Si la fecha/hora del CSV es próxima, esperar a que el scheduler publique y buscar cada `notification_id` en scheduler, platform_campaigns_ms y engine_nlp_ms | Algún componente sin coincidencias. |

## Pasos

1. Firma:
   ```text
   campaigns trace run <archivo.csv> [--timeout 120] [--wait-schedule] [--keep] [--invoke-scheduler]
   ```
   - `--invoke-scheduler`: en lugar de esperar al horario, invoca `scheduler_Lambda` (T-07) después de la etapa 4.
   - Sin `--keep`, al final ofrece borrar los registros de prueba con `dynamo purge` (solo `CLI_TEST_APP_ID`).
2. Cada etapa devuelve `StageResult(name, status, duration, details)`. Si una etapa falla, las siguientes se marcan `OMITIDA`.
3. Mostrar progreso con `rich` (spinner por etapa) en stderr y, al final, la tabla de resultados más los IDs encontrados (para copiarlos en `logs search` o `dynamo get`).
4. Exit code 1 si alguna etapa falla; salida JSON con el `TraceReport` completo.
5. Bloqueado en prod.
6. Al terminar, ejecutarlo en dev con un CSV generado por `csv generate` y dejar la salida como evidencia en `campaigns-cli/evidencias/t09/`.

## Pruebas

- Todos los fakes responden bien → todas las etapas `OK`, exit code 0.
- La ingesta no aparece antes del timeout → etapa 3 `FALLA`, etapas 4–6 `OMITIDA`, exit code 1.
- Dos `campaign_id` distintos para el mismo archivo → etapa 4 `FALLA`.
- Sin `--wait-schedule` ni `--invoke-scheduler` → etapa 6 no se ejecuta y no cuenta como falla.
- Sin `--keep` y con `--yes` → se llama a `purge` con el `campaign_id` encontrado.

## Criterios de terminado

- [ ] `campaigns trace run csv-test.csv` en dev reporta el resultado de cada etapa (criterio de aceptación 4 del plan).
- [ ] Evidencia guardada en `evidencias/t09/`.
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
