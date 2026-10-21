---
id: E-humo
title: "Pruebas de humo (Karate)"
type: epic
---

# Pruebas de humo (Karate)

Escenarios en `queuer_ms/deployment/smokeTest` que confirman tras cada despliegue que las rutas `/api/v1/*` están expuestas, autenticadas y respondiendo, **sin publicar en Kafka** (solo validaciones `400` y health).

Documentación: [guía de pruebas](../../docs/pruebas.md) · [health check](../../docs/publicacion-kafka.md#5-health-check-kafkahealthindicator)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-humo"
SORT id ASC
```
