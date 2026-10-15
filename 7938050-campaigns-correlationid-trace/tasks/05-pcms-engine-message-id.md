# T-05 — platform_campaigns_ms: `message_id` y `campaign_id` en el mensaje al engine

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-7, P-8, P-9
- **Depende de:** T-04, T-01 (confirmación de que engine_nlp_ms tolera `campaign_id`)

> ↩️ **Revertida en [T-17](17-pcms-revertir-correlacion-engine.md) (2026-10-14).** Después de desplegarla, el `traceId` dejó de verse en engine_nlp_ms. El código volvió a su estado anterior a esta task.

## Objetivo

Que el body enviado a engine_nlp_ms por RabbitMQ incluya `data.message_id = notification_id` y `data.campaign_id`.
Hoy engine_nlp_ms usa `notification_id` como `messageId`/`traceId` solo por un fallback implícito (`IncomingMessageParser.withEventFieldsResolved`). Con este cambio, la correlación queda declarada en el contrato y no depende de ese comportamiento interno.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/model/src/main/java/co/com/bancolombia/model/engine/EngineMessage.java` | Agregar `private String messageId;` y `private String campaignId;`. |
| `domain/usecase/src/main/java/co/com/bancolombia/usecase/engine/EngineCampaignSenderUseCase.java` | `buildEngineMessage`: `.messageId(campaignMessage.notificationId())`, `.campaignId(campaignMessage.campaignId())`. Log INFO antes de enviar. |
| `infrastructure/driven-adapters/rabbit-publisher/src/main/java/co/com/bancolombia/events/dto/EngineMessageDto.java` | Agregar `@JsonProperty("message_id") private String messageId;` y `@JsonProperty("campaign_id") private String campaignId;`. |
| `.../rabbit-publisher/.../mapper/EngineMapper.java` | Sin cambio (mapea por nombre). Validar con una prueba. |

## Pasos

1. Agregar los campos al modelo y al DTO.
2. En `EngineCampaignSenderUseCase.buildEngineMessage`, poblar `messageId` y `campaignId`.
3. Agregar un log (el use case usa `@Log` o, si no tiene logger, agregarlo) antes de `serviceEngineGateway.sendMessageToEngine`:
   `"[engine_campaign_sender] Enviando al engine messageId={0}, campaignId={1}, appId={2}, exchange={3}, routingKey={4}"`.
4. No cambiar la firma de `ServiceEngineGateway`: la correlación viaja dentro de `EngineMessage`.

## Pruebas

- `EngineCampaignSenderUseCaseTest`: capturar (`ArgumentCaptor`) el `EngineMessage` enviado al gateway → `messageId == notificationId` y `campaignId == campaignId`.
- `EngineMapperTest`: el DTO contiene `messageId` y `campaignId`. Al serializar con `ObjectMapper`, el JSON tiene las claves `message_id` y `campaign_id`.

## Criterios de terminado

- [x] El JSON de `data` incluye `message_id` y `campaign_id` (prueba de serialización con Jackson 3).
- [x] Se mantiene `notification_id`: engine_nlp_ms lo exige en `IncomingEventValidator.validateRequiredFields`.
- [x] `message_id` siempre igual a `notification_id`: en engine_nlp_ms el valor explícito tiene prioridad sobre el fallback.
- [x] Pruebas en verde: `model` 16, `usecase` 89, `rabbit-publisher` 9, todas sin fallos. Pitest: `EngineCampaignSenderUseCase` 7/7 y `EngineMapperImpl` 14/14 mutantes eliminados (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
