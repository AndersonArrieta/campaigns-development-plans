---
id: B-000
aliases: [B-000]
title: ""
status: todo          # backlog | todo | doing | blocked | done
priority: P1          # P0 | P1 | P2 | P3 (severidad → prioridad)
epic:                 # E-<capacidad afectada>, NO un cajón "E-bugs"
estimate: S           # S | M | L
depends_on: []        # normalmente vacío — un bug suele ser accionable ya
type: bug
affects: []           # [T-0NN, ...] — tarea(s) done cuyo código está implicado
created: 2026-10-13
---

# <Título del bug>

## Reproducción
- **Pasos:**
  1. ...
- **Esperado:** <qué debería pasar>
- **Observado:** <qué pasa en realidad>

## Causa (si se conoce)
-

## Criterios de aceptación
- [ ] El comportamiento observado ya no ocurre.

## Verificación
```bash
# OBLIGATORIO: un test de regresión que falle hoy y pase tras el fix.
uv run pytest tests/test_<modulo>.py -k <nombre_del_test_de_regresion>
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
-
