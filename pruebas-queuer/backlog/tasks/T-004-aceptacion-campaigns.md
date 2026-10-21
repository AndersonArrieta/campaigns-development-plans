---
id: T-004
aliases: [T-004]
title: "Escenarios de aceptación para POST /api/v1/campaigns"
status: backlog
priority: P1
epic: E-aceptacion
estimate: M
depends_on: [T-001, T-002, T-003]
type: task
created: 2026-10-21
---

# T-004 — Escenarios de aceptación para `POST /api/v1/campaigns`

## Objetivo
Automatizar en Karate el contrato de `POST /api/v1/campaigns` contra el ambiente desplegado, en un feature nuevo con tags `@acceptanceTest @campaigns`, reutilizando la obtención de token de `get-token.feature` y las propiedades de [[T-001-parametrizar-karate-config|T-001]] (`baseUrl`, `kafkaReadTimeout`, `kafkaAppId`) con los datos de [[T-003-datos-prueba-kafka-dev|T-003]].

## Documentación relacionada
- [Contrato del endpoint](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Casos C-01 a C-18](../../docs/pruebas.md#post-apiv1campaigns)

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/campaigns_acceptance_test.feature` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/data/campaign-request.json` (nuevo, payload base)

## Tareas
- [ ] Crear `data/campaign-request.json` con el payload completo de la doc; `applicationIdentifier` y `userIdentifier` se sobrescriben en el feature.
- [ ] Crear el feature con `Background`: `configure ssl`, token con `callonce read('get-token.feature')`, `configure readTimeout = kafkaReadTimeout`, `url baseUrl`, `path '/api/v1/campaigns'`, y un body base leído del JSON con `metadata.Id` único por escenario (`java.util.UUID.randomUUID() + ''`), `applicationIdentifier = kafkaAppId` y `userIdentifier = '573000000000'`.
- [ ] Implementar los escenarios de la tabla (cada `400` con **una sola** violación).
- [ ] Dejar fuera los casos con comportamiento observado como defecto (body vacío → `202`, JSON mal formado → `500`): se cubrirán con bugs propios. Anotarlo en un comentario del feature.

| Id | Escenario | Mutación del body base | Esperado |
|---|---|---|---|
| AC-C01 | Validate 202 campaign accepted | — | `202`, `response == { status: 'accepted', message: 'Campaign event accepted for Kafka publication' }` |
| AC-C02 | Validate 202 campaign with only required fields | `remove` `retries`, `node`, `messageContext` | `202` |
| AC-C03 | Validate 400 campaign without metadata | `remove body.metadata` | `400`, `response.error == "El objeto 'metadata' es obligatorio"` |
| AC-C04 | Validate 400 campaign with blank metadata Id | `metadata.Id = '  '` | `400`, `"El campo 'metadata.Id' es obligatorio"` |
| AC-C05 | Validate 400 campaign without data.applicationIdentifier | `remove body.data.applicationIdentifier` | `400`, `"El campo 'data.applicationIdentifier' es obligatorio"` |
| AC-C06 | Validate 400 campaign without data.campaign | `remove body.data.campaign` | `400`, `"El objeto 'data.campaign' es obligatorio"` |
| AC-C07 | Validate 400 campaign without notification dataTime | `remove body.data.campaign.notification.dataTime` | `400`, `"El campo 'data.campaign.notification.dataTime' es obligatorio"` |
| AC-C08 | Validate 400 campaign with metadata in camelCase | renombrar `metadata.Id` → `metadata.id` | `400`, `"El campo 'metadata.Id' es obligatorio"` |
| AC-C09 | Validate 422 campaign with appId without segment | `applicationIdentifier = 'queuer-acceptance-sin-segmento'` | `422`, `"No existe segmento configurado para applicationIdentifier: queuer-acceptance-sin-segmento"` |
| AC-C10 | Validate 403 RBAC campaign | header `Authorization: '123'` | `403`, `response == 'RBAC: access denied'` |

## Criterios de aceptación
- [ ] Los 10 escenarios pasan en `dev` con `--tags @campaigns`.
- [ ] La suite completa de aceptación (incluidos los escenarios de `/queuer`) sigue en verde.
- [ ] Ningún escenario usa un `appId` productivo ni un `userIdentifier` real.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DbaseUrl="$URL_EXT" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  "-Dkarate.options=--tags @campaigns" -i | grep -E "scenarios|passed|failed"
# Suite completa
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DbaseUrl="$URL_EXT" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i | grep -E "scenarios|passed|failed"
```

## Notas
- AC-C08 deja documentado que `metadata` exige PascalCase en la entrada (ver [observación 1](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata) sobre la salida).
