---
id: E-ingesta
title: "Disparo de la ingesta"
type: epic
---

# Disparo de la ingesta

Poner un CSV en el flujo: subirlo al bucket del ingester (grupo `s3`) e invocar `ingester_Lambda` / `scheduler_Lambda` de forma aislada (grupo `lambda`).

Documentación: [recursos AWS § bucket y lambdas](../../docs/recursos-aws.md) · [ADR-0005](../../docs/adr/0005-ingesta-por-s3-y-por-invocacion.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-ingesta"
SORT id ASC
```
