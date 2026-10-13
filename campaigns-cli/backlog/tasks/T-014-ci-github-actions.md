---
id: T-014
aliases: [T-014]
title: "Pipeline de CI en GitHub Actions (lint, tipos, pruebas, cobertura)"
status: todo
priority: P2
epic: E-calidad
estimate: S
depends_on: [T-001]
type: task
origin: tasks/10-documentacion-ci.md
created: 2026-10-13
---

# T-014 — Pipeline de CI en GitHub Actions

## Objetivo
Correr lint, formato, mypy y pruebas con umbral de cobertura en cada cambio de `campaigns-cli/`. El repo está en GitHub (`AndersonArrieta/campaigns-development-plans`), como fija [ADR-0007](../../docs/adr/0007-ubicacion-del-codigo.md).

## Archivos a crear/modificar
- `../.github/workflows/campaigns-cli.yml` (raíz del repo)
- `pyproject.toml` — `[tool.coverage.report] fail_under = 80`
- `docs/desarrollo.md` — sección de CI

## Tareas
- [ ] Workflow con `on: push/pull_request` filtrado a `campaigns-cli/**` y `defaults.run.working-directory: campaigns-cli`.
- [ ] Pasos: `astral-sh/setup-uv`, `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest --cov=campaigns_cli`.
- [ ] Sin credenciales AWS en el pipeline (las pruebas usan moto y fakes).
- [ ] Umbral de cobertura 80 % en `pyproject.toml`.

## Criterios de aceptación
- [ ] Localmente, `pytest --cov` falla si la cobertura baja de 80 %.
- [ ] El workflow corre en verde en GitHub en una rama de prueba.

## Verificación
```bash
uv sync --locked
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest --cov=campaigns_cli
grep -n 'fail_under = 80' pyproject.toml
gh run list --workflow campaigns-cli.yml --limit 1 --json conclusion -q '.[0].conclusion'   # → success
```

## Notas
- Hacer push de la rama para que corra el workflow es una acción hacia afuera: requiere confirmación del usuario.
