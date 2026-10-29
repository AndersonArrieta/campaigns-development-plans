---
id: T-019
aliases: [T-019]
title: "Incluir la suite Queuer en el pipeline de queuer_ms_test"
status: doing
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
- [x] Cambiar las variables del pipeline:
  - `test-runners: IntegratorNode.java,Queuer.java`
  - `test-features: integrator_node.feature,queuer.feature`
- [x] Revisar que `pipelines/build.yaml` conserva ambos (los filtros comparan nombres exactos).
- [ ] Lanzar el pipeline a mano sobre la rama: el trigger solo incluye `refs/heads/trunk` (`feature/*` está comentado). No se descomenta el trigger.
- [x] Listar en `## Notas` las propiedades `-D` que el release debe pasar a la suite `Queuer` y pedir al usuario que las configure.

## Criterios de aceptación
- [ ] El build lanzado a mano sobre la rama muestra `Keeping: Queuer.java` y `Keeping: queuer.feature`.
- [x] La suite `IntegratorNode` sigue incluida.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test/queuer_ms_test
grep -A1 -E 'name: test-(runners|features)' azure-pipeline.yaml
# Esperado: IntegratorNode.java,Queuer.java  /  integrator_node.feature,queuer.feature
```

## Notas
- El trigger del pipeline incluye `Platform_test/*`: los cambios de [[T-016-interaccion-envio-queuer|T-016]] también disparan los pipelines de las demás suites. Es el comportamiento esperado del repo.
- `deploy.yaml` solo corre en `trunk`: el artefacto que usa el release E2E se publica después del merge. Eso condiciona la ejecución desde el release en [[T-020-ejecucion-e2e-qa|T-020]].
- 2026-10-29 — `queuer_ms_test/azure-pipeline.yaml`: `test-runners` = `IntegratorNode.java,Queuer.java` y `test-features` = `integrator_node.feature,queuer.feature` (sin commit). `pipelines/build.yaml` compara nombres exactos separados por coma, así que no necesita cambios. Simulación local de los dos filtros sobre una copia de `Platform_test/src`: `Keeping: IntegratorNode.java`, `Keeping: Queuer.java`, `Keeping: integrator_node.feature`, `Keeping: queuer.feature`, y el artefacto filtrado compila (`compileTestJava` OK).
- Propiedades `-D` que el release E2E del queuer debe pasar a la suite `Queuer` (las mismas de la ejecución local de [[T-017-e2e-notificaciones-queuer|T-017]] y [[T-018-e2e-campanas-queuer|T-018]]):
  - `-Denvironment=qa`
  - `-DappId=others-test`
  - `-DcognitoEndpoint`, `-DclientId`, `-DclientSecret`: los mismos de la suite `Notifications` (cliente `client_credentials` de `chatbots-artemis-qa`).
  - `-DendpointQueuer=https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/queuer/v1` (**nueva**).
  - `-DendpointGetMessageFake=https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/fake-channel/v1` (agregar si el release del queuer no la tiene).
  - No hacen falta `-DonlineNotificationTopic` ni `-DkafkaSecretName`.
  - No usar `--info` en el comando de Gradle del release: imprime la línea del JVM de test con `-DclientSecret`.
- Pendiente (requiere al usuario): commit y push de la rama, lanzar a mano el pipeline `queuer_ms_test` sobre la rama (no hay `az` en esta máquina) y configurar `endpointQueuer` / `endpointGetMessageFake` en las variables del release.
