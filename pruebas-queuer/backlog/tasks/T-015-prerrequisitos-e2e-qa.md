---
id: T-015
aliases: [T-015]
title: "Prerrequisitos E2E en QA: entrada por queuer hasta la entrega en el fakechannel"
status: done
priority: P1
epic: E-e2e
estimate: M
depends_on: [T-008]
type: task
created: 2026-10-22
---

# T-015 — Prerrequisitos E2E en QA: entrada por queuer hasta la entrega en el fakechannel

## Objetivo
Confirmar a mano, en QA, que un evento que entra por `queuer_ms` recorre toda la cadena y llega al fakechannel, antes de automatizarlo:

```
queuer → tópico del segmento → platform_campaigns_ms → adaptador de salida → fakechannel
```

La suite `Notifications` actual publica directo en el tópico `-DonlineNotificationTopic` con el secreto `-DkafkaSecretName`, usando `appId` `others-test`. Hay que verificar que el queuer, al resolver el segmento de ese `appId`, publica en **ese mismo tópico** (y en el equivalente para campañas).

## Documentación relacionada
- [Enrutamiento por segmento](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)
- [Observación 1 — casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata): puede romper la deserialización en el consumidor. Afecta a campañas y a notificaciones: el queuer publica `metadata` en camelCase, mientras que la suite `Notifications` publica en PascalCase (`onlineNotificationEvent.json`).
- [[T-008-exposicion-rutas-qa|T-008]]: host y paths del queuer en QA.
- [[T-009-datos-carga-kafka-qa|T-009]]: configuración de segmentos en QA (mismo item de DynamoDB). Ya confirmó que `others-test` está en el segmento `others`, con `kafka.notifications` = `thirdpartycampaignmanagement.executenotificationv1` y `kafka.campaigns` = `thirdpartycampaignexecution.initiatecampaignv1`.

## Archivos a crear/modificar
- Ninguno en el repo. Los resultados quedan en `## Notas` de esta tarjeta y en `docs/pruebas.md` (tabla de datos E2E).

## Tareas
- [x] Comparar el `kafka.notifications` del segmento `others` (`thirdpartycampaignmanagement.executenotificationv1`, de T-009) con el valor de `onlineNotificationTopic` que usa el release de la suite `Notifications`. El segmento ya está confirmado; solo falta esa comparación.
- [x] Confirmar que `platform_campaigns_ms` en QA consume `thirdpartycampaignexecution.initiatecampaignv1`. T-009 lo dejó sin confirmar porque los tópicos viven en la library del release. Averiguar también qué necesita el consumidor para entregar un `initiatecampaign` recibido por Kafka:
  - si la campaña o la notificación deben existir previamente en DynamoDB, o basta el `node`;
  - qué `identifier` y `node` usar (el dataset `campaigns_e2e_flow` usa el nodo `N-03-99-10`, con texto esperado `Campaig_e2e_test_delivered_successfully`).
- [x] Definir la propiedad del endpoint del queuer para Serenity (propuesta: `-DendpointQueuer=<host><prefijo>`, sin la ruta del recurso).
- [x] Confirmar que el `clientId` de Cognito de las E2E (el mismo de `get-messages`) está autorizado en la `AuthorizationPolicy` del queuer.
- [x] Prueba manual de notificación por WhatsApp: `curl POST <endpointQueuer>/notifications` con `userIdentifier` = `57` + 10 dígitos y `message` único → `202` → `GET <endpointGetMessageFake>/whatsapp/get-messages/<user>` devuelve el texto. Si no se entrega, anotar en el consumidor si el motivo es el casing de `metadata` (observación 1).
- [x] Repetir con campaña, con la misma revisión del casing de `metadata` si no se entrega.

## Criterios de aceptación
- [x] Hay evidencia de una notificación entregada al fakechannel entrando por el queuer, o un motivo concreto de no entrega, registrado como bug `B-0NN` si es un defecto.
- [x] Para campañas hay evidencia de entrega o un motivo concreto de no entrega, registrado como bug `B-0NN` si es un defecto.
- [x] Están documentados `endpointQueuer`, `appId`, los tópicos y el nodo de campaña a usar.

## Verificación
```bash
# TOKEN de Cognito QA con el clientId de las E2E; Q = endpointQueuer; F = endpointGetMessageFake
U="57$(shuf -i 1000000000-9999999999 -n1)"; MSG="Notif_e2e_test_queuer_$(date +%s)"; ID=$(cat /proc/sys/kernel/random/uuid)
curl -s -w ' -> %{http_code}\n' -X POST "$Q/notifications" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"metadata":{"Id":"'"$ID"'","Source":"platform-e2e-test","SpecVersion":"1.0","Type":"notification.execute","DataContentType":"application/json","DataSchema":"https://schema-registry.com","Time":"'"$(date -u +%FT%TZ)"'"},"data":{"userIdentifier":"'"$U"'","sourceChannel":"WhatsApp","applicationIdentifier":"others-test","notification":{"identifier":"'"$ID"'","dataTime":"'"$(date '+%F %T')"'","message":"'"$MSG"'","messageContext":{}}}}'
sleep 20
curl -s "$F/whatsapp/get-messages/$U" -H "Authorization: Bearer $TOKEN" | grep -c "$MSG"   # esperado: 1
```

## Notas
- No se modifica la configuración de segmentos ni los secretos de QA sin confirmación del usuario.
- 2026-10-29 — El usuario confirma que el `clientId` de las E2E es el mismo cliente `client_credentials` de `chatbots-artemis-qa` usado en T-008, que ya pasa la `AuthorizationPolicy` del queuer.
- 2026-10-29 — Revisión del código de `platform_campaigns_ms` (repo `_MR`, rama `trunk`), sin ejecutar nada en QA:
  - El consumidor deserializa `metadata` con `@JsonProperty` en PascalCase (`CampaignEventMetadataDto`), pero usa Jackson 3 (`tools.jackson`), que por defecto ignora propiedades desconocidas, y los casos de uso (`BatchMessageUseCase`, `OnlineMessageUseCase`) solo leen `data` y los headers. Si es así, la [observación 1](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata) deja `metadata` en `null` pero no impide la entrega. Falta confirmarlo con la prueba manual.
  - Una campaña (`initiatecampaign`) no necesita existir antes en DynamoDB: basta con que el mensaje pase `QueueValidatorUseCase.validateWithContext`, que exige `campaign.identifier` y `notification.identifier` como UUID canónicos, `notification.node` con formato `N-00-00-00`, `campaign.retries` entero ≥ 0, `sourceChannel` en `QUEUE-VALIDATION-VALID-CHANNELS` (por defecto `msteams,WhatsApp`) y `userIdentifier` como teléfono (`^\+?\d{7,15}$`) o correo. En el queuer, `retries` y `node` son opcionales: las E2E de campañas deben enviarlos siempre. Si la fecha cae fuera del horario del `appId`, el consumidor reprograma la campaña en DynamoDB en lugar de entregarla.
  - Datos de campaña: nodo `N-03-99-10`, texto esperado `Campaig_e2e_test_delivered_successfully`; en Teams, `userIdentifier` = correo del dataset `campaigns_e2e_flow` de `teams/DataSet.csv` y `sourceChannel` = `msteams`.
  - `requestPrincipals` de la `AuthorizationPolicy` del queuer sale de la variable de release `#{jwt-allowed-request-principals}#`. No se puede leer desde aquí (no hay `az` ni `kubectl` de QA). El cliente `client_credentials` de `chatbots-artemis-qa` usado en [[T-008-exposicion-rutas-qa|T-008]] sí pasa la política.
  - Propuesta de propiedad: `-DendpointQueuer=https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/queuer/v1` (host + prefijo de T-008, sin la ruta del recurso).
- 2026-10-29 — `onlineNotificationTopic` del release de la suite `Notifications` = `thirdpartycampaignmanagement.executenotificationv1`: coincide con `kafka.notifications` del segmento `others`.
- 2026-10-29 — Prueba manual en QA, con aprobación del usuario (token `client_credentials` del cliente de las E2E, `endpointQueuer` = `https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/queuer/v1`, `appId` `others-test`):
  - Notificación WhatsApp: `metadata.Id` `ddb113a7-aa01-4c3f-b4fd-a241cfcaf075`, usuario `571789773445`, mensaje `Notif_e2e_test_queuer_1793291588` → `202 {"status":"accepted","message":"Notification event accepted for Kafka publication"}` en 3,3 s. `GET <endpointGetMessageFake>/whatsapp/get-messages/571789773445` lo devolvió en el primer intento (10 s): `{"text":{"body":"Notif_e2e_test_queuer_1793291588"},"to":"571789773445","type":"text"}`.
  - Campaña WhatsApp: `metadata.Id` `ad293270-a7e4-4d49-a166-0800ce658f59`, `campaign.identifier` `af1a898e-b46c-4a17-bc11-d1d59c0589af`, `notification.identifier` `f1ac74bc-1157-4012-84f7-049e6c61e34e`, `node` `N-03-99-10`, `retries` `0`, usuario `579236115352` → `202 {"status":"accepted","message":"Campaign event accepted for Kafka publication"}` en 1,4 s. El fakechannel devolvió `Campaig_e2e_test_delivered_successfully` en el primer intento.
  - Conclusiones: `platform_campaigns_ms` en QA consume los dos tópicos `thirdparty*` del segmento `others`; el `clientId` de las E2E está autorizado en el queuer; el casing camelCase de `metadata` ([observación 1](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)) no impide la entrega. No se abre bug.
  - Datos registrados en `docs/pruebas.md` (Pruebas E2E → Datos y propiedades).
- No se probó Teams a mano: queda para los escenarios de [[T-017-e2e-notificaciones-queuer|T-017]] y [[T-018-e2e-campanas-queuer|T-018]].
