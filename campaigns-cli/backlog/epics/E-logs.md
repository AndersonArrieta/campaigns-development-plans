---
id: E-logs
title: "Logs de CloudWatch"
type: epic
---

# Logs de CloudWatch

Buscar identificadores y leer eventos en los log groups de los componentes del flujo (grupo `logs`).

Documentación: [recursos AWS § CloudWatch](../../docs/recursos-aws.md#cloudwatch-logs) · [comandos § logs](../../docs/comandos.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-logs"
SORT id ASC
```
