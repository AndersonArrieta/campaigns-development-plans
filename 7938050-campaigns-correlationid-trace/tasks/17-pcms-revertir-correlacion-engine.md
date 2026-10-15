# T-17 — platform_campaigns_ms: revertir `message_id`, `campaign_id` y headers AMQP hacia el engine

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** revierte P-7, P-8, P-9 y P-10
- **Revierte:** T-05 (commit `5c09d97c2`) y T-06 (commit `c81539dcc`)
- **Fecha:** 2026-10-14

## Motivo

Con T-05 y T-06 desplegadas, el `traceId` de la notificación **dejó de verse en engine_nlp_ms**. Antes del ajuste sí aparecía.

En la revisión estática no se encontró una causa en el código:

- engine_nlp_ms deserializa bien el body. `IncomingEventRequestDto` tiene `@JsonIgnoreProperties(ignoreUnknown = true)`, así que `campaign_id` se ignora.
- El `traceId` del engine sale de `message_id`: `EventProcessingContextFactory` y `TraceMdcContext`. Antes llegaba `null` y `IncomingMessageParser.withEventFieldsResolved` lo tomaba de `notification_id`. Con el ajuste llegaba explícito con el mismo valor.
- engine_nlp_ms no lee los headers `CorrelationId`/`campaign_id` ni las propiedades AMQP `messageId`/`correlationId`.

Como no se identificó la causa, se decide **volver al contrato anterior**, que sí funcionaba. engine_nlp_ms sigue usando `notification_id` como `messageId`/`traceId` por su fallback.

## Archivos

Se restauran a su versión anterior a `5c09d97c2` (`git checkout 5c09d97c2^ -- <archivos>`). Ningún commit posterior los había modificado.

| Archivo | Queda así |
|---|---|
| `domain/model/.../engine/EngineMessage.java` | Sin `messageId` ni `campaignId`. |
| `domain/usecase/.../engine/EngineCampaignSenderUseCase.java` | Sin asignar `messageId`/`campaignId` y sin el log `[engine_campaign_sender]` previo al envío. |
| `rabbit-publisher/.../dto/EngineMessageDto.java` | Sin `message_id` ni `campaign_id`. El body solo lleva `notification_id`. |
| `rabbit-publisher/.../EngineMessageSender.java` | Solo el header `x-consumer-id`. Sin `CorrelationId`, sin `campaign_id` y sin las propiedades `messageId`/`correlationId`. Log `[engine_sender]` original. |
| `EngineCampaignSenderUseCaseTest`, `EngineMessageSenderTest`, `EngineMapperTest` | Versión anterior al ajuste. |

Body resultante hacia el engine (igual que antes de T-05):

```json
{
  "eventId": "<uuid evento>",
  "name": "<routingKey>",
  "data": {
    "event_type": "notification",
    "notification_id": "<notification_id>",
    "app_id": "...", "datetime": "...", "user_id": "...", "channel": "...",
    "notification_node": "...", "feedback_url": "...", "context": {}
  }
}
```

## Qué no cambia

- `TraceContext` y los logs `[batch_message_usecase]` (T-03, T-04): siguen registrando `correlationId`, `notificationId` y `campaignId` antes de enviar al engine.
- Flujo online y adapter-out (T-07, T-08), reintentos (T-09).
- engine_nlp_ms: sin cambios.

## Pendiente

- [x] **Documentación del repo (T-10):** `asyncapi.yaml`, `Functionalities.md` y `SequenceDiagrams.md` quedan alineados con el contrato restaurado: sin `message_id`, `campaign_id` ni headers o propiedades AMQP de correlación hacia el engine. Se aclara que engine_nlp_ms usa `notification_id` como `messageId`/`traceId`. YAML válido (2026-10-14).
- [ ] **Causa raíz (opcional):** si se quiere retomar T-05/T-06, comparar en dev el mensaje real en la cola `<engineQueue>_events` y los logs de engine_nlp_ms (`[QueueHandler] Objeto recibido...`, `QueueEventProcessor:received`) con y sin el ajuste.

## Criterios de terminado

- [x] Los 7 archivos quedan como antes de `5c09d97c2`. No quedan referencias a `messageId`/`campaignId` de `EngineMessage` en el código de producción (2026-10-14).
- [ ] Pruebas en verde: `./gradlew :usecase:test :rabbit-publisher:test`. **No se ejecutaron**: en WSL el `JAVA_HOME` apunta a una ruta de Windows y en modo offline falta `tools.jackson.core:jackson-databind:3.1.7` en la caché de Gradle.
- [ ] Commit (lo hace el desarrollador). Mensaje sugerido: `revert(campaigns): dejar de enviar message_id y headers de correlación al engine`.
- [ ] Desplegado en dev y verificado: engine_nlp_ms vuelve a registrar `traceId=<notification_id>`.
