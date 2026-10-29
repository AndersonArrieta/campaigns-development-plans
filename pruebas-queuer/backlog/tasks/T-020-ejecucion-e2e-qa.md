---
id: T-020
aliases: [T-020]
title: "Ejecutar la suite E2E Queuer en QA, evidencias y trazabilidad"
status: backlog
priority: P2
epic: E-e2e
estimate: S
depends_on: [T-019]
type: task
created: 2026-10-22
---

# T-020 — Ejecutar la suite E2E `Queuer` en QA, evidencias y trazabilidad

## Objetivo
Ejecutar la suite `Queuer` desde el release, guardar el reporte de Serenity como evidencia, actualizar el estado en `docs/pruebas.md` y abrir bugs para los defectos confirmados.

## Documentación relacionada
- [Guía de pruebas — E2E](../../docs/pruebas.md#pruebas-e2e-serenity)
- [Observaciones](../../docs/observaciones.md)

## Archivos a crear/modificar
- `docs/pruebas.md`: columna de estado de la tabla E2E, fecha y, si se puede obtener, la versión desplegada del queuer.
- Bugs `B-0NN` en `backlog/bugs/` si aplica.

## Tareas
- [ ] Ejecutar el release E2E del queuer en QA y descargar el reporte agregado de Serenity (`target/site/serenity`). El release necesita el artefacto publicado desde `trunk` (ver [[T-019-pipeline-queuer-ms-test|T-019]]); antes del merge, se ejecuta localmente con las mismas `-D`.
- [ ] Anotar el resultado por escenario (E2E-N01, E2E-N02, E2E-C01, E2E-C02) en `docs/pruebas.md`.
- [ ] Registrar un bug por defecto confirmado, sobre todo si las campañas no se entregan por la observación 1.

## Criterios de aceptación
- [ ] Hay evidencia de una ejecución completa con el resultado de los 4 escenarios.
- [ ] Ninguna fila de la tabla E2E queda en `Planeado`.
- [ ] Las evidencias no contienen tokens ni `clientSecret` (los logs pasan por `LogMasker`).

## Verificación
```bash
cd "/mnt/c/Users/AndersonElitArrietaR/OneDrive - FINAIPRO TECHNOLOGIES SAS/Documentos/campaigns-development-plans/pruebas-queuer"
grep -nE '^\| E2E-' docs/pruebas.md | grep -c Planeado   # esperado: 0
```

## Notas
- Sin contexto `kubectl` de QA, la versión de imagen desplegada puede no ser confirmable (igual que en [[T-008-exposicion-rutas-qa|T-008]]). En ese caso queda pendiente en `## Notas`, sin marcar.
