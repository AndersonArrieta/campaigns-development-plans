---
id: E-aceptacion
title: "Pruebas de aceptación (Karate)"
type: epic
---

# Pruebas de aceptación (Karate)

Escenarios en `queuer_ms/deployment/acceptanceTest` que validan el contrato de `POST /campaigns` y `POST /notifications` contra el ambiente desplegado: publicación exitosa (`202`), validaciones (`400`), destino no resoluble (`422`) y autorización (`403`).

Documentación: [campañas](../../docs/endpoints/POST-api-v1-campaigns.md) · [notificaciones](../../docs/endpoints/POST-api-v1-notifications.md) · [casos de prueba](../../docs/pruebas.md#casos-de-prueba)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-aceptacion"
SORT id ASC
```
