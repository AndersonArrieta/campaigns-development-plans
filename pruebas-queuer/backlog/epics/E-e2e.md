---
id: E-e2e
title: "Pruebas E2E funcionales (Serenity)"
type: epic
---

# Pruebas E2E funcionales (Serenity)

Flujo completo en **QA**:

1. Petición HTTP a `queuer_ms` (`POST /api/v1/notifications` o `POST /api/v1/campaigns`).
2. Tópico Kafka.
3. `platform_campaigns_ms`.
4. Adaptador de salida.
5. Fakechannel: se verifica que el mensaje llegó al usuario de prueba (`get-messages`).

El código vive en el repo `NU0284001_Artemis_Chatbots_Platform_MR_Test`:
- `Platform_test/`: proyecto Serenity + Cucumber + Screenplay compartido por todas las suites.
- `queuer_ms_test/`: solo el pipeline, que copia `Platform_test` y deja únicamente los runners y features listados en `test-runners` / `test-features`.

Se reutiliza la suite `Notifications` existente (que publica directo en Kafka): `PrepareNotificationEvent`, `VerifyChannelDelivery`, `Cognito` y los datasets `notifications_e2e_flow` / `campaigns_e2e_flow`. Lo nuevo es la entrada por el queuer en lugar de publicar en Kafka.

Documentación: [guía de pruebas — E2E](../../docs/pruebas.md#pruebas-e2e-serenity) · [contrato de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md) · [contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-e2e"
SORT id ASC
```
