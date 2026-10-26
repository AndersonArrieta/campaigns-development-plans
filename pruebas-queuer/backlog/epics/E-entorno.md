---
id: E-entorno
title: "Entorno y precondiciones de prueba"
type: epic
---

# Entorno y precondiciones de prueba

Lo que debe existir antes de que un escenario Karate pueda pasar: parametrización de los proyectos `acceptanceTest`/`smokeTest` (URL base, timeouts), exposición de `/campaigns` y `/notifications` por Istio y Cognito, y datos de prueba en `dev` (segmento con bloque `kafka`, secreto y tópicos).

Documentación: [publicación en Kafka](../../docs/publicacion-kafka.md) · [guía de pruebas](../../docs/pruebas.md#prerrequisitos)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-entorno"
SORT id ASC
```
