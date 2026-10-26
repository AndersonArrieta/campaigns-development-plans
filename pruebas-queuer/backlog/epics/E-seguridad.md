---
id: E-seguridad
title: "Seguridad del contenedor de queuer_ms (DevSecOps)"
type: epic
---

# Seguridad del contenedor de `queuer_ms` (DevSecOps)

Hallazgos del análisis de contenedor (`DevSecOps Engine Tool - engine_container`, Prisma Cloud/twistcli) que bloquean el release de `queuer_ms` y, con él, la ejecución en `dev` de las suites de aceptación y humo. Los hallazgos vienen de la imagen base (JDK Corretto y paquetes de Amazon Linux 2023), no del código del microservicio ni de las pruebas.

Criterio de falla del engine: `very critical >= 2`, `critical >= 4`, `high >= 8` o `medium low >= 15` (operador `or`), sin contar los hallazgos exceptuados vigentes.

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-seguridad"
SORT id ASC
```
