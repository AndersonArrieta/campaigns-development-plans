---
id: E-humo
title: "Pruebas de humo (Karate)"
type: epic
---

# Pruebas de humo (Karate)

Escenarios en `queuer_ms/deployment/smokeTest` que confirman tras cada despliegue que el servicio responde, **sin publicar en Kafka**. Hoy solo valida el health (SM-01): los escenarios de `/campaigns` y `/notifications` se eliminaron en [[T-024-eliminar-humo-campaigns-notifications|T-024]] y esas rutas quedan cubiertas por la suite de aceptación.

Documentación: [guía de pruebas](../../docs/pruebas.md) · [health check](../../docs/publicacion-kafka.md#5-health-check-kafkahealthindicator)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-humo"
SORT id ASC
```
