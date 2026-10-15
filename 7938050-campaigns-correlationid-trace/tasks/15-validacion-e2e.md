# T-15 — Validación de punta a punta en dev

- **Componente:** Todos
- **Ítems del plan:** §6 (Integración / aceptación), §9 (Criterios de aceptación)
- **Depende de:** T-01 … T-14 y T-16 desplegadas en dev (sin T-16 solo se puede validar el paso 6 como "fallo conocido")

## Objetivo

Demostrar que con un solo `notification_id` se reconstruye el recorrido completo en los logs, incluidos los reintentos.

## Pasos

1. **Ingester:** cargar un CSV de prueba (2 o 3 usuarios, varias horas) en el bucket de dev.
   - Anotar el `campaign_id` (log `[Campaign ...]`) y 2 `notification_id` desde la tabla de campañas.
2. **Scheduler:** esperar o forzar la ejecución en la hora programada.
   - En CloudWatch: `Message published to Kafka` con `Correlation Id = <notification_id>` y `Campaign Id = <campaign_id>`.
3. **platform_campaigns_ms:** logs `[batch_message_usecase] ... correlationId=<notification_id>, ..., campaignId=<campaign_id>`. No debe aparecer `correlationId=null`.
   - Log `[engine_sender]` con `notification_id=<notification_id>` en el body (T-17: ya no se envía `messageId`).
4. **engine_nlp_ms:** logs `[QueueHandler] Objeto recibido...` con `notification_id` en el payload (sin `message_id` ni `campaign_id`, ver T-17), y `QueueEventProcessor:received` y `[MSG_TRACE]` con `traceId=<notification_id>` en el MDC.
5. **Adapter out (batch, vía engine_nlp_ms):** en el log `publish:serialized`, `OutboundEngineResponse.message_id=<notification_id>`, y el adapter o mapper_out del canal registra ese mismo id.
6. **Reintento** (requiere T-16): provocar una `NullSessionException` (notificación a un usuario sin sesión o conversación).
   - engine_nlp_ms registra `notifyCampaignReschedule` con `traceId=<notification_id>` y `POST /v1/retry` responde 200.
   - `[retry_handler]` y `RetryUseCase` registran `correlationId=<notification_id>`, `retries=1` y la nueva `datetime`.
   - En el siguiente ciclo del scheduler se emite el mismo `CorrelationId`.
7. **Flujo online:** publicar un evento online de prueba.
   - El registro en el topic adapter-out tiene el header `CorrelationId`, key = `notification_id` y `metadata.MessageIdentifier = notification_id`.
8. **Fuera de horario:** enviar una notificación fuera del cron del app_id → log de reprogramación con `correlationId` y `campaignId`, y el ítem en Dynamo conserva `notification_id` y `campaign_id`.
9. **Consulta única:** en el agregador de logs, filtrar por un `notification_id` y guardar la consulta y la evidencia (capturas o export).

## Evidencias

| Paso | Componente | Evidencia (enlace / captura) | OK |
|---|---|---|---|
| 1 | ingester | | ☐ |
| 2 | scheduler | | ☐ |
| 3 | platform_campaigns_ms | | ☐ |
| 4 | engine_nlp_ms | | ☐ |
| 5 | adapter out | | ☐ |
| 6 | reintento | | ☐ |
| 7 | online | | ☐ |
| 8 | fuera de horario | | ☐ |
| 9 | consulta única | | ☐ |

## Criterios de terminado (§9 del plan)

- [ ] Todo mensaje del scheduler lleva `CorrelationId = notification_id` y `campaign_id`.
- [ ] platform_campaigns_ms registra `correlationId` (nunca `null`) y `campaignId` en batch, online y reintentos.
- [ ] El mensaje al engine tiene `data.notification_id` y engine_nlp_ms registra `traceId = notification_id` (T-17: sin `message_id` ni headers AMQP de correlación).
- [ ] El mensaje al adapter-out tiene `MessageIdentifier = notification_id` y el header `CorrelationId`.
- [ ] Recorrido completo reconstruible con un solo `notification_id`.
- [ ] Evidencias adjuntas a la HU 7938050. Aprobación para promover a QA.
