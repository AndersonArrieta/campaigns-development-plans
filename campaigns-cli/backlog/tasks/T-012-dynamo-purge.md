---
id: T-012
aliases: [T-012]
title: "Comando dynamo purge para limpiar datos de prueba"
status: todo
priority: P1
epic: E-dynamo
estimate: M
depends_on: [T-006]
type: task
affects: [T-006]
origin: tasks/06-dynamo-commands.md
created: 2026-10-13
---

# T-012 — Comando `dynamo purge` para limpiar datos de prueba

## Objetivo
Borrar de la tabla de campañas los registros que deja una prueba, para que `trace run` ([[T-009-trace-run|T-009]]) limpie al terminar. Amplía `dynamo_service.py` de [[T-006-dynamo-lectura|T-006]], que quedó de solo lectura.

## Archivos a crear/modificar
- `src/campaigns_cli/services/dynamo_service.py` — `purge_campaign(campaign_id, test_app_id) -> PurgeResult`
- `src/campaigns_cli/commands/dynamo_cmd.py` — subcomando `purge`
- `tests/test_dynamo_service.py`, `tests/test_dynamo_cmd.py`
- `README.md` — sección de `dynamo purge`
- `docs/comandos.md`, `docs/configuracion.md` (permiso `BatchWriteItem`)

## Tareas
- [ ] `dynamo purge --campaign-id ID`: busca los registros con `find_by_campaign` (GSI o scan con aviso).
- [ ] `ensure_not_prod` + `confirm_destructive` mostrando cuántos registros se borrarán.
- [ ] Solo borra registros con `app_id == CLI_TEST_APP_ID`; los demás se omiten y se reportan.
- [ ] `batch_write_item` en lotes de 25, reintentando `UnprocessedItems` con espera creciente.
- [ ] Resultado: borrados, omitidos (otro `app_id`) y fallidos; tabla o JSON.

## Criterios de aceptación
- [ ] Con moto: borra solo los registros de `CLI_TEST_APP_ID` y deja los demás.
- [ ] Más de 25 registros → varios lotes, todos borrados.
- [ ] `UnprocessedItems` simulado → se reintenta hasta borrarlos.
- [ ] Respuesta "n" a la confirmación → no borra nada (exit 0); con `--yes` no pregunta.
- [ ] `CAMPAIGNS_ENV=prod` → bloqueado (exit 2).
- [ ] La tabla de logs no se toca.

## Verificación
```bash
uv run pytest tests/test_dynamo_service.py tests/test_dynamo_cmd.py -q -k purge
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Ejecutarlo contra dev borra datos reales: solo con confirmación del usuario y sobre campañas de `CLI_TEST_APP_ID`.
