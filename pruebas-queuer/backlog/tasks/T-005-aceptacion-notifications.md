---
id: T-005
aliases: [T-005]
title: "Escenarios de aceptación para POST /api/v1/notifications"
status: backlog
priority: P1
epic: E-aceptacion
estimate: M
depends_on: [T-001, T-002, T-003]
type: task
created: 2026-10-21
---

# T-005 — Escenarios de aceptación para `POST /api/v1/notifications`

## Objetivo
Automatizar en Karate el contrato de `POST /api/v1/notifications` contra el ambiente desplegado, en un feature nuevo con tags `@acceptanceTest @notifications`, con la misma estructura que [[T-004-aceptacion-campaigns|T-004]] (puede ejecutarse en paralelo con ella).

## Documentación relacionada
- [Contrato del endpoint](../../docs/endpoints/POST-api-v1-notifications.md)
- [Casos N-01 a N-06](../../docs/pruebas.md#post-apiv1notifications)

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/notifications_acceptance_test.feature` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/data/notification-request.json` (nuevo, payload base)

## Tareas
- [ ] Crear `data/notification-request.json` con el payload completo de la doc.
- [ ] Crear el feature con el mismo `Background` que campañas, con `path '/api/v1/notifications'`, `metadata.Id` único, `applicationIdentifier = kafkaAppId`, `userIdentifier = '573000000000'`.
- [ ] Implementar los escenarios de la tabla (cada `400` con **una sola** violación).
- [ ] Dejar fuera body vacío y JSON mal formado (ver [observaciones 2 y 3](../../docs/observaciones.md#2-body-vacío-responde-202-sin-publicar)), con comentario en el feature.

| Id | Escenario | Mutación del body base | Esperado |
|---|---|---|---|
| AC-N01 | Validate 202 notification accepted | — | `202`, `response == { status: 'accepted', message: 'Notification event accepted for Kafka publication' }` |
| AC-N02 | Validate 202 notification without messageContext | `remove body.data.notification.messageContext` | `202` |
| AC-N03 | Validate 400 notification without metadata | `remove body.metadata` | `400`, `"El objeto 'metadata' es obligatorio"` |
| AC-N04 | Validate 400 notification with blank metadata Id | `metadata.Id = '  '` | `400`, `"El campo 'metadata.Id' es obligatorio"` |
| AC-N05 | Validate 400 notification without data.notification | `remove body.data.notification` | `400`, `"El objeto 'data.notification' es obligatorio"` |
| AC-N06 | Validate 400 notification without message | `remove body.data.notification.message` | `400`, `"El campo 'data.notification.message' es obligatorio"` |
| AC-N07 | Validate 400 notification without userIdentifier | `remove body.data.userIdentifier` | `400`, `"El campo 'data.userIdentifier' es obligatorio"` |
| AC-N08 | Validate 422 notification with appId without segment | `applicationIdentifier = 'queuer-acceptance-sin-segmento'` | `422`, `"No existe segmento configurado para applicationIdentifier: queuer-acceptance-sin-segmento"` |
| AC-N09 | Validate 403 RBAC notification | header `Authorization: '123'` | `403`, `response == 'RBAC: access denied'` |

## Criterios de aceptación
- [ ] Los 9 escenarios pasan en `dev` con `--tags @notifications`.
- [ ] La suite completa de aceptación sigue en verde.
- [ ] Ningún escenario usa un `appId` productivo ni un `userIdentifier` real.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DbaseUrl="$URL_EXT" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  "-Dkarate.options=--tags @notifications" -i | grep -E "scenarios|passed|failed"
```

## Notas
- `data/` comparte carpeta con el payload de campañas de T-004; si T-004 ya la creó, solo agregar el archivo.
