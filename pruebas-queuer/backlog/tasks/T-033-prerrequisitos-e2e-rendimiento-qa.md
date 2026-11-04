---
id: T-033
aliases: [T-033]
title: "Prerrequisitos de las pruebas E2E de rendimiento por el queuer en QA"
status: done
priority: P1
epic: E-e2e-rendimiento
estimate: S
depends_on: []
type: task
created: 2026-11-04
---

# T-033 — Prerrequisitos de las pruebas E2E de rendimiento por el queuer en QA

## Objetivo
Confirmar lo que necesitan los grupos E2E de rendimiento por el queuer antes de modificar los `.jmx`: host del queuer alcanzable desde el agente del release, cliente Cognito autorizado, datos de prueba y aval del equipo consumidor para la carga.

Ya está confirmado y no se repite:
- `performance_test` (appId de `DT_Campaigns.txt`) está en el segmento `others` de QA, con `kafka.campaigns` = `thirdpartycampaignexecution.initiatecampaignv1` y `kafka.notifications` = `thirdpartycampaignmanagement.executenotificationv1` ([[T-009-datos-carga-kafka-qa|T-009]]). Son los mismos tópicos por defecto de `V_campaignsTopic` / `V_notificationsTopic` en los scripts E2E.
- El queuer responde en `https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/queuer/v1` y `platform_campaigns_ms` entrega en el fakechannel los eventos que entran por él ([[T-008-exposicion-rutas-qa|T-008]], [[T-015-prerrequisitos-e2e-qa|T-015]]).

## Documentación relacionada
- [Guía de pruebas — modulares, datos en QA](../../docs/pruebas.md#datos-de-prueba-en-qa)
- [Guía de pruebas — E2E, datos y propiedades](../../docs/pruebas.md#datos-y-propiedades)
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)

## Archivos a crear/modificar
- `docs/pruebas.md` (nueva sección de pruebas E2E de rendimiento con los datos confirmados)

## Tareas
- [x] Confirmar el host del queuer para los scripts E2E: estos usan `informacion-int-qa` (`V_server`) para el fakechannel; comprobar si el queuer responde también por `int-qa` o si hay que usar `ext-qa`.
- [x] Confirmar que el cliente Cognito de los scripts E2E (`cognitoId` del release de WhatsApp y de Teams) pasa la `AuthorizationPolicy` del queuer. Puede no ser el mismo cliente de las E2E Serenity.
- [x] Confirmar que el token de `Tx_oauthToken` (`props.access_token`) sirve para el queuer y para `get-messages` a la vez.
- [ ] Identificar el release que ejecuta `SC_whatsappJMeterTest.jmx` y `SC_teamsJMeterTest.jmx` y cómo pasa las propiedades (`-J`), para definir las nuevas en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]].
- [ ] Acordar con el equipo de `platform_campaigns_ms` los TPS y la duración máximos, igual que en [[T-009-datos-carga-kafka-qa|T-009]].

## Criterios de aceptación
- [x] Una campaña y una notificación de WhatsApp enviadas a mano por el queuer, con el host y el cliente Cognito de los scripts E2E y el appId `performance_test`, responden `202` y llegan al fakechannel.
- [ ] Host, cliente, propiedades del release y límites de carga quedan registrados en `docs/pruebas.md`.

## Verificación
```bash
# Con el token del cliente Cognito de los scripts E2E (no imprimir el secreto)
curl -s -o /dev/null -w '%{http_code}\n' -X POST "https://<host-queuer>/artemis/platform/queuer/v1/notifications" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d @notification-performance_test.json
# Esperado: 202, y el mensaje en GET https://informacion-int-qa.apps.ambientesbc.com/artemis/platform/fake-channel/v1/whatsapp/get-messages/<userIdentifier>
```

## Notas
- Cada `202` produce un mensaje real que procesa `platform_campaigns_ms` en QA. Los envíos manuales requieren aprobación del usuario.
- No se modifica la configuración de segmentos ni los secretos de QA sin confirmación del usuario.
- 2026-11-04 — Revisión de los scripts E2E (rama `feature/8016357-queuer-e2e-performance-test` del repo PE), sin publicar nada:
  - `Tx_oauthToken` pide el token con `client_credentials` usando `cognitoId` / `cognitoSecret` / `cognitoServer` / `cognitoPath` y lo deja en `props.access_token`. La verificación en el fakechannel (`ReqInteraction2*`) usa ese mismo token, así que el queuer debe aceptarlo. Los valores los pone el release y no están en el repo.
  - El release que ejecuta `SC_whatsappJMeterTest.jmx` / `SC_teamsJMeterTest.jmx` no está versionado: `azure-pipelines.yaml` → `pipelines/deploy.yaml` solo construye el artefacto. Las propiedades `-J` se definen en el release clásico de Azure DevOps (no hay `az` aquí).
  - `V_server` por defecto = `informacion-int-qa.apps.ambientesbc.com` en los dos scripts. `GH_setup` corre `Tx_secretManager` con `stoptest`: los grupos del queuer necesitan que la identidad del release lea el secreto Kafka aunque los grupos directos estén en `0`.
- 2026-11-04 — Sondeos sin publicar (`POST {}`) a `/artemis/platform/queuer/v1/{campaigns,notifications}`:
  - `ext-qa` sin token → `403 RBAC: access denied` (igual que en [[T-008-exposicion-rutas-qa|T-008]]).
  - `int-qa` resuelve a IPs internas (`10.104.92.122`, `10.104.93.197`) y presenta un certificado de una CA interna (`self-signed certificate in certificate chain`). No se pudo sondear sin desactivar la validación TLS, y esa acción se denegó en la sesión. El sampler HTTP de JMeter acepta cualquier certificado, así que esto no afecta a los scripts.
  - No hay credenciales Cognito de QA en local: `queuer-cognito-recipe-test/config.env` apunta a `chatbots-artemis-dev`.
- ~~**Bloqueada:**~~ (resuelto abajo) faltaban (1) un token o las credenciales QA del `cognitoId` del release E2E de JMeter, para confirmar la `AuthorizationPolicy` del queuer y `get-messages` con el mismo token; (2) permiso para sondear `int-qa` con `-k` o con el CA interno; (3) el nombre del release y sus variables; (4) los TPS y la duración máximos acordados con el equipo de `platform_campaigns_ms`; (5) aprobación para el envío manual de una campaña y una notificación (`202` reales en QA).
- 2026-11-04 — Credenciales de `queuer-qa.env` (cliente `client_credentials` de `chatbots-artemis-qa`). El usuario confirma que es el mismo `cognitoId` del release E2E de JMeter. Sondeos sin publicar por `ext-qa`: `POST {}` a `/campaigns` → `400 El objeto 'data' es obligatorio` y a `/notifications` → `400 El objeto 'metadata' es obligatorio` (pasa la `AuthorizationPolicy`); `GET get-messages` de un usuario sin mensajes → `404 No messages found`. El mismo token sirve para el queuer y el fakechannel.
- 2026-11-04 — `int-qa`: el certificado lo emite `ROOTBANCOLOMBIABC` → `SUBCABANCOLOMBIABC` → `SUBCABANCOLOMBIABC1`. Esa raíz no está en el almacén de Windows, así que no se pudo validar sin desactivar TLS. Decisión: `V_queuerServer` = `informacion-ext-qa.apps.ambientesbc.com`, ya verificado para el queuer y el fakechannel. Queda pendiente si el queuer también responde por `int-qa`.
- 2026-11-04 — Envío manual en QA, con aprobación del usuario (`ext-qa`, `appId` `performance_test`):
  - Notificación WhatsApp: `metadata.Id` `17da4cde-6f25-41e9-a727-438035c90374`, usuario `577640130326`, mensaje `Notif_qe2e_t033_1793827639` → `202 accepted` en 3,9 s. `get-messages` lo devolvió en el primer intento (10 s).
  - Campaña WhatsApp: `metadata.Id` `7aa919eb-7cd5-4922-8e5a-7563c83e815d`, `campaign.identifier` `8bd1f6f3-3d26-4ec0-974c-639697b37aa0`, `notification.identifier` `beecd7e9-a035-434c-a67b-d0aaf7f479b5`, nodo `N-03-99-10`, `retries` `0`, usuario `579249190373` → `202 accepted` en 0,4 s. `get-messages` devolvió `Campaig_e2e_test_delivered_successfully` en el primer intento.
  - Datos registrados en `docs/pruebas.md` (Pruebas E2E de rendimiento → Datos y propiedades de rendimiento).
- **Cerrada en `done` con pendientes** (igual que T-008/T-009). Siguen sin marcar: el nombre del release E2E de JMeter y cómo pasa las propiedades; los TPS y la duración máximos acordados con `platform_campaigns_ms`; si el queuer responde por `int-qa`; que la identidad del release pueda leer el secreto Kafka. T-034 puede avanzar, pero T-037 no debe correr carga por encima de 1 TPS sin los límites acordados.
