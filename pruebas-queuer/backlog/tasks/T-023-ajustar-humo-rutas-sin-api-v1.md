---
id: T-023
aliases: [T-023]
title: "Ajustar las pruebas de humo a /campaigns y /notifications"
status: blocked
priority: P1
epic: E-humo
estimate: S
depends_on: [T-021]
affects: [T-006]
type: task
created: 2026-10-26
---

# T-023 — Ajustar las pruebas de humo a `/campaigns` y `/notifications`

## Objetivo
SM-02 y SM-03 de [[T-006-humo-endpoints-kafka|T-006]] llaman `/api/v1/campaigns` y `/api/v1/notifications`. Con [[T-021-quitar-prefijo-api-v1|T-021]] esas rutas responden `404` y el release de humo falla, que es justo para lo que se diseñaron. Esta tarjeta cambia los paths a `/campaigns` y `/notifications`. Los payloads sin `metadata` y la aserción `400` siguen igual, así que el humo sigue sin publicar en Kafka.

Va en la **misma rama y PR** que T-021.

## Documentación relacionada
- [Escenarios de humo](../../docs/pruebas.md) (tabla SM-01 a SM-03)
- [Health check y estado agregado](../../docs/publicacion-kafka.md#5-health-check-kafkahealthindicator)

## Archivos a crear/modificar
- `queuer_ms/deployment/smokeTest/src/test/resources/co/com/bancolombia/smoke_test.feature`
- `queuer_ms/deployment/smokeTest/README.md` (fila `baseUrl` de la tabla de propiedades)
- `pruebas-queuer/docs/pruebas.md` (filas SM-02 y SM-03)

## Tareas
- [x] `smoke_test.feature`: `path '/api/v1/campaigns'` → `path '/campaigns'` y `path '/api/v1/notifications'` → `path '/notifications'`. No cambiar los nombres de los escenarios, que no incluyen la ruta.
- [x] No tocar `Validate health` (SM-01), los payloads ni `karate-config.js`.
- [x] README de `smokeTest`: en la fila `baseUrl`, "rutas `/api/v1/campaigns` y `/api/v1/notifications`" → "rutas `/campaigns` y `/notifications`".
- [x] `docs/pruebas.md`: SM-02 → `POST /campaigns` sin `metadata`, SM-03 → `POST /notifications` sin `metadata`, enlazando esta tarjeta.
- [x] Confirmar que no queda `/api/v1` en el proyecto: `grep -rn "api/v1" queuer_ms/deployment/smokeTest` sin resultados.

## Criterios de aceptación
- [ ] Con T-021 desplegada en `dev`: 4/4 (`get-token` + SM-01, SM-02, SM-03) solo con los parámetros actuales del release.
- [ ] Con `-DbaseUrl="$URL_EXT/ruta-no-expuesta"`, SM-02 y SM-03 fallan con `404` y la suite falla, igual que en T-006.
- [ ] Ningún escenario de humo publica en Kafka.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/smokeTest
grep -rn "api/v1" . --include=*.feature --include=*.md --include=*.js   # sin resultados
./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i \
  | grep -E "scenarios|passed|failed"
# Negativo: debe fallar con 404 en SM-02 y SM-03
./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" -DbaseUrl="$URL_EXT/ruta-no-expuesta" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i \
  | grep -E "scenarios|passed|failed|status code was"
```

## Notas
- **Solo se valida en `dev`.** En local solo se revisa con `grep` que no quede `/api/v1`. La tarjeta se cierra con la suite de humo en verde en `dev` una vez desplegada la rama de T-021. Hasta entonces queda `blocked` con esa nota. Antes del despliegue, SM-02 y SM-03 fallan con `404` por diseño.
- T-006 es `done` y no se edita. Esta tarjeta la enlaza con `affects`.
- SM-02 y SM-03 están en `feature/7978714_queuer_smoke_tests` y, por el merge `73f59c186`, también en `feature/7978702_queuer_acceptance_tests`. Ninguna de las dos está en `trunk`. Se trabaja en la rama que defina T-021.
- Riesgo conocido de SM-01 (`503` si el `KafkaHealthIndicator` quedó en `DOWN`): sin cambios, ver T-006.
- 2026-10-26 — Ejecutada con T-021 en `blocked`, igual que T-022, porque las tres van en el mismo PR. Rama `feature/7978702_queuer_acceptance_tests`, sin commit.
- Cambios: `path` de SM-02 (`/campaigns`) y SM-03 (`/notifications`) en `smoke_test.feature`, conservando CRLF, y la fila `baseUrl` del README de `smokeTest`. `Validate health`, payloads, nombres de escenario y `karate-config.js` sin cambios. `grep "api/v1"` sobre las fuentes de `smokeTest` no da resultados (solo aparece en `build/`, que es una copia de una compilación previa).
- `docs/pruebas.md`: SM-02 y SM-03 pasan a `POST /campaigns` y `POST /notifications`, con enlace a esta tarjeta junto a T-006.
- **blocked:** falta desplegar T-021 en `dev` y correr la suite de humo (4/4) y el caso negativo con `-DbaseUrl` a una ruta no expuesta (SM-02 y SM-03 con `404`).
