---
id: T-024
aliases: [T-024]
title: "dynamo clean sin confirmación"
status: done
priority: P2
epic: E-dynamo
estimate: S
depends_on: [T-020]
type: task
affects: [T-020]
created: 2026-10-16
---

# T-024 — `dynamo clean` sin confirmación

## Objetivo
`dynamo clean` se corre antes de cada prueba en dev; que no pida confirmación ni haga falta
`--yes`. Amplía [[T-020-dynamo-historial-y-limpieza|T-020]]. Decisión en
[ADR-0012](../../docs/adr/0012-dynamo-clean-sin-confirmacion.md), que reemplaza a ADR-0011.

## Archivos a crear/modificar
- `src/campaigns_cli/commands/dynamo_cmd.py` — `clean` sin `confirm_destructive`; informa qué borra
- `tests/test_dynamo_cmd.py`
- `docs/adr/0012-dynamo-clean-sin-confirmacion.md`, `docs/adr/0011-vaciado-de-tablas-en-dev.md` (`superseded`), `docs/adr/README.md`
- `docs/comandos.md`, `docs/arquitectura.md`, `README.md`

## Tareas
- [x] Quitar la confirmación de `clean`; antes de borrar, mensaje con filas, alcance, entorno y tablas.
- [x] Mantener el bloqueo en prod, el plan, `--dry-run` y la verificación final.
- [x] ADR-0012 y ADR-0011 → `superseded`.
- [x] Actualizar la documentación.

## Criterios de aceptación
- [x] `dynamo clean` sin `--yes` y sin entrada vacía las dos tablas (moto) y no pregunta.
- [x] `--dry-run` sigue sin borrar; prod sigue bloqueado (exit 2).
- [x] `dynamo purge` sigue pidiendo confirmación.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_dynamo_cmd.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Pedido del usuario (2026-10-16).
- **Cierre (2026-10-16):** verificación local en verde (427 pruebas; ruff y mypy).
