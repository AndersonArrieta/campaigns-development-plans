---
id: T-019
aliases: [T-019]
title: "Incluir la suite Queuer en el pipeline de queuer_ms_test"
status: backlog
priority: P1
epic: E-e2e
estimate: S
depends_on: [T-017, T-018]
type: task
created: 2026-10-22
---

# T-019 — Incluir la suite `Queuer` en el pipeline de `queuer_ms_test`

## Objetivo
`queuer_ms_test/azure-pipeline.yaml` hoy solo publica `IntegratorNode.java` / `integrator_node.feature`. Hay que agregar la suite nueva para que el artefacto E2E del queuer la incluya, y dejar declaradas las propiedades que necesita en la ejecución del release.

## Documentación relacionada
- [Guía de pruebas — E2E](../../docs/pruebas.md#pruebas-e2e-serenity)

## Archivos a crear/modificar
- `queuer_ms_test/azure-pipeline.yaml`: `test-runners` y `test-features`.
- Variables del release E2E del queuer (fuera del repo): `endpointQueuer`, y `endpointGetMessageFake` si no existe. **Requiere confirmación del usuario.**

## Tareas
- [ ] Cambiar las variables del pipeline:
  - `test-runners: IntegratorNode.java,Queuer.java`
  - `test-features: integrator_node.feature,queuer.feature`
- [ ] Revisar que `pipelines/build.yaml` conserva ambos (los filtros comparan nombres exactos).
- [ ] Listar en `## Notas` las propiedades `-D` que el release debe pasar a la suite `Queuer` y pedir al usuario que las configure.

## Criterios de aceptación
- [ ] El build del pipeline en la rama muestra `Keeping: Queuer.java` y `Keeping: queuer.feature`.
- [ ] La suite `IntegratorNode` sigue incluida.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test/queuer_ms_test
grep -A1 -E 'name: test-(runners|features)' azure-pipeline.yaml
# Esperado: IntegratorNode.java,Queuer.java  /  integrator_node.feature,queuer.feature
```

## Notas
- El trigger del pipeline incluye `Platform_test/*`: los cambios de [[T-016-interaccion-envio-queuer|T-016]] también disparan los pipelines de las demás suites. Es el comportamiento esperado del repo.
