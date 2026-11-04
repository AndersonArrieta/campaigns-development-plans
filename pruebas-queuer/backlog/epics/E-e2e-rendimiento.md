---
id: E-e2e-rendimiento
title: "Pruebas E2E de rendimiento por el queuer (JMeter)"
type: epic
---

# Pruebas E2E de rendimiento por el queuer (JMeter)

Carga E2E en **QA** de `POST /campaigns` y `POST /notifications` de `queuer_ms`, desde la petición HTTP hasta la entrega en el fakechannel:

```
queuer (HTTP) → Kafka → platform_campaigns_ms → adaptador de salida → fakechannel (get-messages)
```

El código vive en el repo `NU0284001_Artemis_Chatbots_Platform_PE`, en los scripts E2E existentes:
- `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx`
- `Back/E2E/teams/SC_teamsJMeterTest.jmx`

Esos scripts ya traen `GH_campaigns` y `GH_notifications`, que hacen el mismo flujo pero **publicando directo en Kafka** (`ReqPublishAndValidate*Kafka`), verifican la entrega con `ReqInteraction2*` y validan los tópicos al cierre en `GH_tearDownKafkaValidation`. Esta épica agrega grupos nuevos que entran por el queuer y reutilizan el setup (`Tx_oauthToken`, `Tx_secretManager`), los datasets y la verificación en el fakechannel. Los grupos existentes no cambian de comportamiento.

Enabler de Azure DevOps: *Pruebas E2E de rendimiento de POST /campaigns y POST /notifications de queuer_ms*.

Documentación: [contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md) · [contrato de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md) · [pruebas modulares](../../docs/pruebas.md#pruebas-modulares-jmeter) · [pruebas E2E Serenity](../../docs/pruebas.md#pruebas-e2e-serenity) · [observación 5 (latencia)](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)

## Tareas
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE epic = "E-e2e-rendimiento"
SORT id ASC
```
