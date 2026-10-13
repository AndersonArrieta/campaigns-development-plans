---
id: E-dynamo
title: "Consulta y limpieza en DynamoDB"
type: epic
---

# Consulta y limpieza en DynamoDB

Tabla de campañas y tabla de logs del ingester: buscar, listar, seguir cargas y limpiar datos de prueba (grupo `dynamo`).

Documentación: [recursos AWS § tablas](../../docs/recursos-aws.md) · [comandos § dynamo](../../docs/comandos.md) · [ADR-0004](../../docs/adr/0004-busquedas-sin-gsi.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-dynamo"
SORT id ASC
```
