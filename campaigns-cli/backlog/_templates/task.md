---
id: T-000
aliases: [T-000]
title: ""
status: backlog       # backlog | todo | doing | blocked | done
priority: P2          # P0 | P1 | P2 | P3
epic:                 # E-base | E-csv | E-ingesta | E-dynamo | E-logs | E-trace | E-calidad | E-entrega
estimate: M           # S | M | L
depends_on: []        # [T-0NN, ...]
type: task
created: 2026-10-13
---

# <Título>

## Objetivo
<Qué se consigue y por qué.>

## Archivos a crear/modificar
- `ruta/al/archivo`

## Tareas
- [ ] ...
- [ ] (si cambia el comportamiento) Actualizar `docs/` (comandos, configuración, recursos AWS…)
- [ ] (si cambia una decisión de arquitectura) Escribir ADR en `docs/adr/`

## Criterios de aceptación
- [ ] ...

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
-
