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
created: 2026-10-21
---

# B-000 — <Título del bug>

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
# Unitario: cd queuer_ms && ./gradlew test --tests '<Clase>'
# Karate:   cd queuer_ms/deployment/acceptanceTest && ./gradlew clean test "-Dkarate.options=--tags @<tag>" ...
```

## Notas
-
