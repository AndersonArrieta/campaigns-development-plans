---
id: T-033
aliases: [T-033]
title: "Prerrequisitos de las pruebas E2E de rendimiento por el queuer en QA"
status: todo
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

## Archivos a crear/modificar
- `docs/pruebas.md` (nueva sección de pruebas E2E de rendimiento con los datos confirmados)

## Tareas
- [ ] Confirmar el host del queuer para los scripts E2E: estos usan `informacion-int-qa` (`V_server`) para el fakechannel; comprobar si el queuer responde también por `int-qa` o si hay que usar `ext-qa`.
- [ ] Confirmar que el cliente Cognito de los scripts E2E (`cognitoId` del release de WhatsApp y de Teams) pasa la `AuthorizationPolicy` del queuer. Puede no ser el mismo cliente de las E2E Serenity.
- [ ] Confirmar que el token de `Tx_oauthToken` (`props.access_token`) sirve para el queuer y para `get-messages` a la vez.
- [ ] Identificar el release que ejecuta `SC_whatsappJMeterTest.jmx` y `SC_teamsJMeterTest.jmx` y cómo pasa las propiedades (`-J`), para definir las nuevas en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]].
- [ ] Acordar con el equipo de `platform_campaigns_ms` los TPS y la duración máximos, igual que en [[T-009-datos-carga-kafka-qa|T-009]].

## Criterios de aceptación
- [ ] Una campaña y una notificación de WhatsApp enviadas a mano por el queuer, con el host y el cliente Cognito de los scripts E2E y el appId `performance_test`, responden `202` y llegan al fakechannel.
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
