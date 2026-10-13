---
id: T-009
aliases: [T-009]
title: "Prueba de punta a punta trace run (CSV → S3 → Dynamo → logs del ingester)"
status: backlog
priority: P1
epic: E-trace
estimate: L
depends_on: [T-004, T-005, T-006, T-008, T-012]
type: task
origin: tasks/09-trace-run.md
created: 2026-10-13
---

# T-009 — Prueba de punta a punta `trace run`

## Objetivo
Encadenar los servicios existentes en una sola prueba que suba un CSV, confirme que el ingester creó los registros en DynamoDB y verifique que su `campaign_id` aparece en los logs del ingester, con un reporte OK/FALLA por etapa (criterio de aceptación 4 del plan, hasta el ingester). La parte aguas abajo (scheduler y microservicios) es [[T-013-trace-aguas-abajo|T-013]].

| # | Etapa | Cómo se verifica | Falla si |
|---|---|---|---|
| 1 | Validar CSV | `csv_service.validate_csv` | Hay errores de formato. |
| 2 | Subir a S3 | `S3Service.upload`; se guarda la hora de subida `t0` | Error de S3. |
| 3 | Ingesta | Polling de la tabla de logs (`app_id` del CSV, cargas después de `t0`) y de `DynamoService.list_range` filtrando por `app_id` y los `usuario` del CSV | No aparecen todos los registros antes del timeout, o la carga queda con estado de error. |
| 4 | Identificadores | Un solo `campaign_id` para el archivo y un `notification_id` por usuario y fecha/hora | Más de un `campaign_id` o faltan `notification_id`. |
| 5 | Logs del ingester | `LogsService.search` por `campaign_id` en el log group del ingester | Sin coincidencias. |

## Archivos a crear/modificar
- `src/campaigns_cli/services/trace_service.py` — `TraceService(csv, s3, dynamo, logs, settings)` con `run(path, options) -> TraceReport`; `StageResult(name, status, duration, details)`
- `src/campaigns_cli/commands/trace_cmd.py` — subgrupo `trace` con `run`
- `src/campaigns_cli/main.py` — registrar el subgrupo `trace`
- `tests/test_trace_service.py`, `tests/test_trace_cmd.py`
- `docs/comandos.md`, `docs/arquitectura.md`, `docs/README.md` (estado de `trace` y criterio 4)

## Tareas
- [ ] `trace run <archivo.csv> [--timeout 120] [--keep]`; `--timeout` por defecto `CLI_WAIT_TIMEOUT_SECONDS`, polling cada `CLI_POLL_INTERVAL_SECONDS`.
- [ ] Si una etapa falla, las siguientes quedan `OMITIDA`.
- [ ] Progreso con `rich` en stderr; al final, tabla de etapas y los IDs encontrados (para `logs search` / `dynamo get`).
- [ ] Sin `--keep`, al final ofrece borrar los registros de prueba con el purge de [[T-012-dynamo-purge|T-012]] (solo `CLI_TEST_APP_ID`; `--yes` omite la pregunta).
- [ ] Exit code 1 si alguna etapa falla; `--output json` devuelve el `TraceReport` completo.
- [ ] Bloqueado en prod.
- [ ] Ejecutarlo en dev con un CSV de `csv generate` y guardar la salida en `evidencias/t009/` (sin credenciales ni ARNs completos).

## Criterios de aceptación
- [ ] Fakes que responden bien → todas las etapas `OK`, exit code 0.
- [ ] La ingesta no aparece antes del timeout → etapa 3 `FALLA`, 4–5 `OMITIDA`, exit code 1.
- [ ] Dos `campaign_id` distintos para el mismo archivo → etapa 4 `FALLA`.
- [ ] Sin `--keep` y con `--yes` → se llama a `purge` con el `campaign_id` encontrado; con `--keep`, no.
- [ ] En dev, `trace run` reporta OK en las 5 etapas y la evidencia queda en `evidencias/t009/`.

## Verificación
```bash
uv run pytest tests/test_trace_service.py tests/test_trace_cmd.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
# en dev (requiere confirmación del usuario: dispara la ingesta real)
mkdir -p evidencias/t009
uv run campaigns csv generate --users 573232540390 --canal WhatsApp --fecha mañana --hora 10 --nodo N-03-99-10 -o evidencias/t009/campaign.csv
uv run campaigns --yes trace run evidencias/t009/campaign.csv --timeout 180 2>&1 | tee evidencias/t009/trace-run.txt
```

## Notas
- La fecha `mañana` evita que el scheduler envíe el mensaje durante la prueba; el purge final lo limpia de la tabla.
- Necesita en el `.env` de dev: `CAMPAIGNS_INPUT_BUCKET`, `CAMPAIGNS_TABLE_NAME`, `CAMPAIGNS_LOGS_TABLE_NAME` e `INGESTER_LAMBDA_NAME`.
