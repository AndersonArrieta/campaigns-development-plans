---
id: E-base
title: "Base de la CLI"
type: epic
---

# Base de la CLI

Esqueleto uv, carga del `.env` (`Settings`), fábrica de clientes AWS, salida tabla/JSON, traducción de errores a exit codes y protecciones de entorno (prod, confirmaciones). Incluye el grupo `config`.

Documentación: [arquitectura](../../docs/arquitectura.md) · [configuración](../../docs/configuracion.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-base"
SORT id ASC
```
