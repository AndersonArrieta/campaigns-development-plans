---
id: E-trace
title: "Prueba de punta a punta"
type: epic
---

# Prueba de punta a punta

Orquestar CSV → S3 → Dynamo → logs en un solo comando con reporte por etapa (grupo `trace`).

Documentación: [criterios de aceptación](../../docs/README.md#criterios-de-aceptación-del-proyecto)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-trace"
SORT id ASC
```
