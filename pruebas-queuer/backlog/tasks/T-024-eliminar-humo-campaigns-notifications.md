---
id: T-024
aliases: [T-024]
title: "Eliminar los escenarios de humo de /campaigns y /notifications"
status: backlog
priority: P1
epic: E-humo
estimate: S
depends_on: []
affects: [T-006, T-023]
type: task
created: 2026-10-26
---

# T-024 — Eliminar los escenarios de humo de `/campaigns` y `/notifications`

## Objetivo
Cambio solicitado: quitar de `smokeTest` los escenarios SM-02 (`Validate campaigns route is exposed`) y SM-03 (`Validate notifications route is exposed`), que agregó [[T-006-humo-endpoints-kafka|T-006]] y ajustó [[T-023-ajustar-humo-rutas-sin-api-v1|T-023]]. La suite de humo vuelve a tener solo `Validate health` (SM-01), como antes de T-006.

La exposición de `/campaigns` y `/notifications` queda cubierta por la suite de aceptación ([[T-022-ajustar-aceptacion-rutas-sin-api-v1|T-022]]). Un `404` en esas rutas hace fallar AC-C01 y AC-N01.

## Documentación relacionada
- [Escenarios de humo](../../docs/pruebas.md) (tabla SM-01 a SM-03)
- Estado del feature antes de T-006: commit `a89bbb4be^` en `NU0284001_Artemis_Chatbots_Platform_MR`

## Archivos a crear/modificar
- `queuer_ms/deployment/smokeTest/src/test/resources/co/com/bancolombia/smoke_test.feature`
- `queuer_ms/deployment/smokeTest/src/test/resources/karate-config.js` (solo si se quita `baseUrl`, ver tareas)
- `queuer_ms/deployment/smokeTest/README.md` (fila `baseUrl`, solo si se quita)
- `pruebas-queuer/docs/pruebas.md` (tabla de humo y frase "Los escenarios de humo no publican en Kafka")
- `pruebas-queuer/backlog/epics/E-humo.md` (descripción)

## Tareas
- [ ] Trabajar en la rama que defina el usuario. Hoy los escenarios viven en `feature/7978702_queuer_acceptance_tests` (y SM-02/SM-03 originales en `feature/7978714_queuer_smoke_tests`).
- [ ] En `smoke_test.feature`, quitar los escenarios `Validate campaigns route is exposed` y `Validate notifications route is exposed`, con sus payloads. Mantener `@smokeTest`, el `Background` y `Validate health` sin cambios. Conservar CRLF.
- [ ] Decidir con el usuario si se quita también `baseUrl` del `karate-config.js` y del README de `smokeTest`. Se agregó en [[T-001-parametrizar-karate-config|T-001]] solo para estas rutas y queda sin uso. Si se quita, `kafkaReadTimeout` sigue igual: verificar si `smokeTest` también lo usa y quitarlo solo si tampoco tiene uso.
- [ ] `docs/pruebas.md`: quitar SM-02 y SM-03 de la tabla de humo (o marcarlas `Eliminado` con enlace a esta tarjeta) y ajustar el texto que sigue a la tabla.
- [ ] `E-humo.md`: la descripción deja de mencionar las rutas `/campaigns` y `/notifications`.
- [ ] Confirmar con `grep -rn "campaigns\|notifications" queuer_ms/deployment/smokeTest/src` que no quedan referencias.

## Criterios de aceptación
- [ ] `smoke_test.feature` queda con un solo escenario (`Validate health`) y sin referencias a `/campaigns` ni `/notifications`.
- [ ] En `dev`, la suite de humo pasa con los parámetros actuales del release: 2/2 (`get-token` + SM-01).
- [ ] El release de humo no necesita variables nuevas ni pierde ninguna que use.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/smokeTest
grep -rn "campaigns\|notifications\|api/v1" src   # sin resultados
# dev (con la rama desplegada): esta es la validacion que cierra la tarjeta
./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i \
  | grep -E "scenarios|passed|failed"
```

## Notas
- **Solo se valida en `dev`.** En local solo se revisa con `grep`. La tarjeta se cierra con la suite de humo en verde en `dev`. Si la rama aún no está desplegada, queda en `blocked` con esa nota.
- T-006 es `done` y no se edita. T-023 queda superada por esta tarjeta: sus cambios de ruta desaparecen al eliminar los escenarios.
- Riesgo conocido de SM-01 (`503` si el `KafkaHealthIndicator` quedó en `DOWN`): sin cambios, ver T-006.
