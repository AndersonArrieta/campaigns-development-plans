---
id: E-calidad
title: "Calidad, validación y documentación"
type: epic
---

# Calidad, validación y documentación

Validación contra AWS real en dev, pipeline de CI y documentación de uso.

Documentación: [desarrollo](../../docs/desarrollo.md) · [ADR-0007](../../docs/adr/0007-ubicacion-del-codigo.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-calidad"
SORT id ASC
```
