---
id: E-trazabilidad
title: "Evidencias y trazabilidad"
type: epic
---

# Evidencias y trazabilidad

Ejecución de las suites en `dev`, archivo de reportes como evidencia y trazabilidad entre los casos de [docs/pruebas.md](../../docs/pruebas.md), los escenarios Karate y las tarjetas del backlog.

Documentación: [guía de pruebas](../../docs/pruebas.md) · [observaciones](../../docs/observaciones.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-trazabilidad"
SORT id ASC
```
