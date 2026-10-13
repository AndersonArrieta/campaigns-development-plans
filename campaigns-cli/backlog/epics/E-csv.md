---
id: E-csv
title: "Archivos CSV de campaña"
type: epic
---

# Archivos CSV de campaña

Generar y validar CSV con el formato que acepta `ingester_Lambda` (grupo `csv`), sin AWS.

Documentación: [comandos § grupos planeados](../../docs/comandos.md#grupos-planeados)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-csv"
SORT id ASC
```
