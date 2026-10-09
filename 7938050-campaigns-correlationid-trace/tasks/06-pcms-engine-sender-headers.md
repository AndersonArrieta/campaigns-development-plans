# T-06 — platform_campaigns_ms: headers AMQP de correlación en `EngineMessageSender`

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-10
- **Depende de:** T-05

## Objetivo

Propagar la correlación también en los metadatos del mensaje RabbitMQ (headers y propiedades AMQP), no solo en el body.

## Archivos

| Archivo | Cambio |
|---|---|
| `infrastructure/driven-adapters/rabbit-publisher/src/main/java/co/com/bancolombia/events/EngineMessageSender.java` | Headers, props y log. |
| `infrastructure/driven-adapters/rabbit-publisher/src/test/java/co/com/bancolombia/events/EngineMessageSenderTest.java` | Ajustar y ampliar. |

## Pasos

1. Construir los headers:
   ```java
   Map<String, Object> headers = new HashMap<>();
   headers.put("x-consumer-id", consumerId);
   putIfNotBlank(headers, "CorrelationId", message.getMessageId());
   putIfNotBlank(headers, "campaign_id", message.getCampaignId());
   ```
2. Propiedades AMQP:
   ```java
   new AMQP.BasicProperties.Builder()
       .headers(headers)
       .messageId(message.getMessageId())
       .correlationId(message.getMessageId())
       .build();
   ```
3. `eventId` del wrapper `EngineMessageDataDto` **sigue siendo `UUID.randomUUID()`** (decisión D-2).
4. Actualizar el log `[engine_sender]` con `messageId` y `campaignId`. Si el body completo puede tener datos sensibles en `context`, evaluar con el equipo bajarlo a DEBUG. No es obligatorio en esta task.

## Pruebas (`EngineMessageSenderTest`)

- Capturar el `OutboundMessage` enviado al `Sender` y verificar:
  - headers `x-consumer-id`, `CorrelationId == notificationId`, `campaign_id`;
  - `properties.getMessageId()` y `properties.getCorrelationId()` == notificationId;
  - el body JSON contiene `data.message_id`.
- `messageId == null` → no se agregan los headers de correlación y no hay NPE.

## Criterios de terminado

- [x] Headers y props AMQP presentes (`CorrelationId`, `campaign_id`, `x-consumer-id`; props `messageId`/`correlationId`). Se omiten si vienen vacíos.
- [x] Pruebas en verde: `rabbit-publisher` 12 pruebas, 0 fallos. `EngineMessageSender`: 100 % de líneas y ramas, 7/7 mutantes eliminados (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
