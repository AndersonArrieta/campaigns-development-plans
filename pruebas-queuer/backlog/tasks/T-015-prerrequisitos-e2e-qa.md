---
id: T-015
aliases: [T-015]
title: "Prerrequisitos E2E en QA: entrada por queuer hasta la entrega en el fakechannel"
status: backlog
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
- [Observación 1 — casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata): puede romper la deserialización en el consumidor.
- [[T-008-exposicion-rutas-qa|T-008]]: host y paths del queuer en QA.
- [[T-009-datos-carga-kafka-qa|T-009]]: configuración de segmentos en QA (mismo item de DynamoDB).

## Archivos a crear/modificar
- Ninguno en el repo. Los resultados quedan en `## Notas` de esta tarjeta y en `docs/pruebas.md` (tabla de datos E2E).

## Tareas
- [ ] Confirmar en la configuración de segmentos de QA (solo lectura) el segmento de `others-test` y que su `kafka.notifications` coincide con el `onlineNotificationTopic` de la suite `Notifications`.
- [ ] Identificar el tópico `kafka.campaigns` de ese segmento y averiguar qué necesita `platform_campaigns_ms` para entregar un `initiatecampaign` recibido por Kafka:
  - si la campaña o la notificación deben existir previamente en DynamoDB, o basta el `node`;
  - qué `identifier` y `node` usar (el dataset `campaigns_e2e_flow` usa el nodo `N-03-99-10`, con texto esperado `Campaig_e2e_test_delivered_successfully`).
- [ ] Definir la propiedad del endpoint del queuer para Serenity (propuesta: `-DendpointQueuer=<host><prefijo>`, sin la ruta del recurso).
- [ ] Confirmar que el `clientId` de Cognito de las E2E (el mismo de `get-messages`) está autorizado en la `AuthorizationPolicy` del queuer.
- [ ] Prueba manual de notificación por WhatsApp: `curl POST <endpointQueuer>/notifications` con `userIdentifier` = `57` + 10 dígitos y `message` único → `202` → `GET <endpointGetMessageFake>/whatsapp/get-messages/<user>` devuelve el texto.
- [ ] Repetir con campaña. Si no se entrega, anotar en el consumidor si el motivo es el casing de `metadata` (observación 1).

## Criterios de aceptación
- [ ] Hay evidencia de una notificación entregada al fakechannel entrando por el queuer.
- [ ] Para campañas hay evidencia de entrega o un motivo concreto de no entrega, registrado como bug `B-0NN` si es un defecto.
- [ ] Están documentados `endpointQueuer`, `appId`, los tópicos y el nodo de campaña a usar.

## Verificación
```bash
# TOKEN de Cognito QA con el clientId de las E2E; Q = endpointQueuer; F = endpointGetMessageFake
U="57$(shuf -i 1000000000-9999999999 -n1)"; MSG="Notif_e2e_test_queuer_$(date +%s)"; ID=$(uuidgen)
curl -s -w ' -> %{http_code}\n' -X POST "$Q/notifications" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"metadata":{"Id":"'"$ID"'","Source":"platform-e2e-test","SpecVersion":"1.0","Type":"notification","DataContentType":"application/json","DataSchema":"https://schema-registry.com","Time":"'"$(date -u +%FT%TZ)"'"},"data":{"userIdentifier":"'"$U"'","sourceChannel":"WhatsApp","applicationIdentifier":"others-test","notification":{"identifier":"'"$ID"'","dataTime":"'"$(date '+%F %T')"'","message":"'"$MSG"'","messageContext":{}}}}'
sleep 20
curl -s "$F/whatsapp/get-messages/$U" -H "Authorization: Bearer $TOKEN" | grep -c "$MSG"   # esperado: 1
```

## Notas
- No se modifica la configuración de segmentos ni los secretos de QA sin confirmación del usuario.
