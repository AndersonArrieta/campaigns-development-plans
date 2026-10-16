---
id: T-023
aliases: [T-023]
title: "dynamo list sin fecha: todas las filas de las tablas de campañas y de logs"
status: done
priority: P2
epic: E-dynamo
estimate: S
depends_on: [T-006, T-020]
type: task
affects: [T-006]
created: 2026-10-16
---

# T-023 — `dynamo list` sin fecha: todas las filas de las dos tablas

## Objetivo
Con `uv run campaigns dynamo list` sin opciones, ver todo lo que hay en la tabla de campañas y en la
de logs, sin tener que acordarse de `dump`. Amplía [[T-006-dynamo-lectura|T-006]]; reutiliza el
`dump` de [[T-020-dynamo-historial-y-limpieza|T-020]].

## Archivos a crear/modificar
- `src/campaigns_cli/commands/dynamo_cmd.py` — `list` sin fecha delega en `_dump_tables` (extraído de `dump`)
- `src/campaigns_cli/services/dynamo_service.py` — `CampaignsTable.all(..., user=)`
- `tests/test_dynamo_cmd.py`
- `docs/comandos.md`, `README.md`

## Tareas
- [x] `dynamo list` sin `--date`, `--hour`, `--from` ni `--to`: scan de las dos tablas, con la misma salida que `dump` (tabla por tabla; en JSON `{campaigns, logs}`).
  - `--app-id` filtra las dos; `--user` solo la de campañas (los logs no tienen usuario).
  - `-n` es el máximo por tabla; sin él, todas las filas.
- [x] Con fecha, el comportamiento de T-006 no cambia (`-n` por defecto 500); `--hour` sin `--date` sigue usando hoy.
- [x] Actualizar `docs/comandos.md` y `README.md`.

## Criterios de aceptación
- [x] `dynamo list` devuelve las 5 filas de campañas y las 3 de logs (moto) y avisa del scan.
- [x] `--app-id`, `--user` y `-n` filtran o limitan como se describe.
- [x] `list --date`, `--hour` y `--from/--to` dan los mismos resultados que antes.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_dynamo_cmd.py -q
uv run campaigns dynamo list --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Pedido del usuario (2026-10-16). Cambia el significado de `dynamo list` sin argumentos: antes era "lo programado hoy"; ahora eso es `dynamo list --date <hoy>`.
- En JSON, `list` sin fecha devuelve un objeto `{campaigns, logs}` y no una lista como con fecha.
- **Cierre (2026-10-16):** verificación local en verde (427 pruebas, cobertura 97 %; ruff y mypy).
