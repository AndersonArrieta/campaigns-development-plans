---
id: T-006
aliases: [T-006]
title: "Escenarios de humo para /api/v1/campaigns y /api/v1/notifications"
status: done
priority: P1
epic: E-humo
estimate: S
depends_on: [T-001, T-002]
type: task
created: 2026-10-21
---

# T-006 — Escenarios de humo para `/api/v1/campaigns` y `/api/v1/notifications`

## Objetivo
Agregar a `smokeTest` escenarios que confirmen tras cada despliegue que las dos rutas nuevas están expuestas, autenticadas y llegan al `Handler`, **sin publicar en Kafka**: se envía un payload completo salvo `metadata`, que la aplicación rechaza con `400` antes de resolver segmento o tocar el broker. Esto sirve en cualquier ambiente, incluido producción.

## Documentación relacionada
- [Respuestas del endpoint de campañas](../../docs/endpoints/POST-api-v1-campaigns.md#respuestas)
- [Respuestas del endpoint de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md#respuestas)
- [Health check y estado agregado](../../docs/publicacion-kafka.md#5-health-check-kafkahealthindicator)

## Archivos a crear/modificar
- `queuer_ms/deployment/smokeTest/src/test/resources/co/com/bancolombia/smoke_test.feature`

## Tareas
- [x] Agregar tag `@smokeTest` al feature (si no lo tiene) sin cambiar el escenario `Validate health`.
- [x] Agregar los escenarios de la tabla usando `url baseUrl` + `path`.
- [x] Payloads en línea en el feature, con `applicationIdentifier: 'smoke-test'` y sin `metadata` (no hace falta `kafkaAppId`).

| Id | Escenario | Request | Esperado |
|---|---|---|---|
| SM-01 | Validate health (existente) | `GET endpoint` | `200`, `$..status contains "UP"` |
| SM-02 | Validate campaigns route is exposed | `POST /api/v1/campaigns`, body sin `metadata` | `400`, `response.error == "El objeto 'metadata' es obligatorio"` |
| SM-03 | Validate notifications route is exposed | `POST /api/v1/notifications`, body sin `metadata` | `400`, `response.error == "El objeto 'metadata' es obligatorio"` |

## Criterios de aceptación
- [x] Los 3 escenarios pasan en `dev`.
- [x] Ningún escenario de humo produce mensajes en Kafka (todos cortan en validación).
- [x] Un `404` en SM-02/SM-03 hace fallar la suite (detecta rutas no expuestas por el VirtualService).

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/smokeTest
./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" -DbaseUrl="$URL_EXT" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i \
  | grep -E "scenarios|passed|failed"
```

## Notas
- Riesgo conocido para SM-01: si una publicación previa falló, el `KafkaHealthIndicator` queda en `DOWN` y `/actuator/health` responde `503` hasta el siguiente envío exitoso ([observación 8](../../docs/observaciones.md#8-health-global-y-sensible-a-errores-de-negocio)). No se modifica el escenario; si ocurre, registrar un bug.
- 2026-10-23 — Implementado en la rama `feature/7978714_queuer_smoke_tests` (sin commit del feature). Esa rama sale de `trunk` y no tenía la parametrización de `karate-config.js`; por decisión del usuario se hizo cherry-pick del commit de parametrización (`d77fb4ebf` → `b40665e29`).
- Verificación en `dev` solo con los parámetros actuales del release (`endpoint` de health + Cognito, `baseUrl` derivada): 4/4 (`get-token` + SM-01, SM-02, SM-03).
- Con `-DbaseUrl="$URL_EXT/ruta-no-expuesta"`: SM-02 y SM-03 fallan con `status code was: 404, expected: 400` y el build falla, así que un `404` sí hace fallar la suite.
- Los payloads no llevan `metadata`, así que cortan en la validación y no publican en Kafka. El release de humo no necesita variables nuevas.
