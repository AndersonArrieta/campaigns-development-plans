# T-01 — Validaciones previas con consumidores

- **Componente:** engine_nlp_ms, whatsapp_adapter_out_ms, teams_adapter_out_ms, webchat_adapter_out_ms (solo lectura y pruebas locales)
- **Ítems del plan:** §2.4, §2.5, §5 (D-1…D-6), §8 (Riesgos)
- **Depende de:** —
- **Bloquea:** T-05 (campos nuevos en el body hacia el engine), T-07 (cambio de `MessageIdentifier`), T-16 (decisión D-6)

## Objetivo

Confirmar que los cambios de contrato son seguros para los consumidores downstream antes de modificar código.

## Pasos

1. **engine_nlp_ms: lectura del body** (`infrastructure/entry-points/async-event-bus/.../rabbit/handler/`)
   - `IncomingMessageParser` lee con `FAIL_ON_UNKNOWN_PROPERTIES` activado. Confirmar con una prueba unitaria local (sin commit, o agregándola en T-16) que un payload con `data.campaign_id` y `data.message_id` se deserializa sin error gracias a `@JsonIgnoreProperties(ignoreUnknown = true)` de `IncomingEventRequestDto`:
     ```java
     // IncomingMessageParserTest
     String body = """
       {"eventId":"e1","name":"rk","data":{"event_type":"notification","app_id":"APP",
        "user_id":"u","channel":"msteams","notification_id":"N1","message_id":"N1",
        "campaign_id":"C1","notification_node":"n","feedback_url":"http://x/v1/retry",
        "datetime":"2026-10-08 10:00:00","context":{}}}""";
     IncomingEventRequestDto dto = parser.readValidatedEvent(rabbitMessage(body));
     assertEquals("N1", dto.getMessageId());
     ```
   - Confirmar que, si `message_id` está presente, `withEventFieldsResolved` lo respeta, y que `TraceLogEvent` y `EventProcessingContextFactory` usan ese valor como `traceId`.
2. **engine_nlp_ms: headers AMQP**
   - Confirmar que para `event_type=notification` no se validan headers (`processNotification` no llama `validateConsumerId`) y que los headers o props nuevos (`CorrelationId`, `campaign_id`, `messageId`, `correlationId`) no afectan `RabbitMessage`.
3. **engine_nlp_ms: feedback de reintento (§2.5 del plan)**
   - Reproducir con una prueba o en local la serialización de `NotificationEndpoint.notifyCampaignReschedule`: ¿qué body llega realmente a `POST /v1/retry`?
   - Registrar la evidencia (excepción del encoder, `{}` o 400) para justificar T-16.
4. **Adapters out: deduplicación**
   - En `whatsapp_adapter_out_ms`, `teams_adapter_out_ms` y `webchat_adapter_out_ms`, buscar usos de `MetadataDto.messageId` (`MessageIdentifier`): idempotencia, deduplicación, claves de caché o de tablas.
   - Si alguno deduplica por `MessageIdentifier`, evaluar el impacto: en el flujo online, cada `notification_id` genera un solo mensaje.
5. **Productores del topic online (D-5)**
   - Identificar quién publica en el topic online de platform_campaigns_ms y si envía `CorrelationId` y con qué valor.
6. **Decisiones D-1 a D-6**
   - Validar con el equipo y dejar el resultado registrado en esta task.

## Resultado (ejecutado el 2026-10-08)

### Cómo se validó

- Artifactory (`artifactory.apps.bancolombia.com`) no es accesible desde el entorno de análisis, así que no se pudo compilar engine_nlp_ms tal cual.
- Se armó un proyecto Gradle mínimo que compila las **clases reales de engine_nlp_ms sin modificar**:
  - Clases incluidas: `IncomingMessageParser`, `IncomingEventRequestDto`, `IncomingRequestDto`, `NotificationEndpoint`, `TraceLog*`, `RequestTree`, `TraceCollector`, `TraceNode` y `TraceEvent`.
  - Versiones iguales a las del servicio, resueltas desde Maven Central: Spring Boot BOM 4.1.1 (spring-webflux 7.0.9; Jackson 3 `tools.jackson` 3.1.5 en runtime), Jackson 2.22.3, Lombok 1.18.42 y reactive-commons 7.0.6.
- Evidencia en [`../evidencias/t01/`](../evidencias/t01/): `build.gradle`, las pruebas `IncomingMessageParserT01Test` y `NotificationEndpointT01Test`, y [`salida-pruebas.txt`](../evidencias/t01/salida-pruebas.txt).
  - Para repetirla: copiar esas clases desde engine_nlp_ms a `src/main/java` y las pruebas a `src/test/java`, y ejecutar `gradle test`.

### Tabla de resultados

| Validación | Resultado | Observaciones |
|---|---|---|
| engine_nlp_ms deserializa con `campaign_id`/`message_id` en el body | ☑ **OK** (prueba) | `@JsonIgnoreProperties(ignoreUnknown = true)` del DTO prevalece sobre `FAIL_ON_UNKNOWN_PROPERTIES` del `ObjectReader`. `campaign_id` se ignora sin error. |
| engine_nlp_ms respeta `message_id` explícito como `traceId` | ☑ **OK** (prueba + código) | Sin `message_id` → `messageId = notification_id` (contrato actual). Con `message_id` explícito, gana el explícito (prueba con `"otro-id"`). `EventProcessingContextFactory` y `TraceLogEvent.of(fn, requestTree)` usan `messageId` como `traceId`. ⇒ En T-05, `message_id` **debe** ser igual a `notification_id`. |
| engine_nlp_ms tolera los headers/props AMQP nuevos | ☑ **OK** (prueba + bytecode) | La cola de eventos se consume con `HandlerRegistry.listenQueue(...)` → `QueueHandler::handleMessageEvents` (mensaje raw). `processNotification` no valida headers. En reactive-commons 7.0.6, la única correlación es el header `x-correlation-id` (`org.reactivecommons.async.commons.Headers`), usado solo en query/reply. `async-rabbit` no lee las props `correlationId`/`messageId`. ⚠️ **No usar el nombre `x-correlation-id`** en P-10: usar `CorrelationId`. |
| Feedback de reintento de engine_nlp_ms (§2.5) | ☒ **Roto, confirmado** (prueba) → **T-16** | `notifyCampaignReschedule` **no falla** en engine_nlp_ms: el encoder Jackson 3 de WebClient serializa el builder de Lombok como **`{}`** (`Content-Type: application/json`). Ese body no tiene `notification_id` ni `datetime`, así que `Handler.isValidPayload` de platform_campaigns_ms lo rechaza con **400 Bad Request**: los reintentos por `NullSessionException` nunca se reprograman. El `NotificationEndpointTest` existente no lo detecta porque mockea `bodyValue(any())`. |
| Adapters out no deduplican por `MessageIdentifier` | ☑ **OK** (código) | **whatsapp_adapter_out_ms:** `EventMapper` copia `MessageIdentifier` → `EngineEvent.messageId` y no tiene más usos. **teams_adapter_out_ms:** se usa como `TeamsFrom.id` (campo `from.id` de la actividad enviada a Bot Framework). **webchat_mapper_out_ms:** se envía como `MessageId` en el payload REST. Sin lógica de dedupe ni idempotencia en ninguno (búsqueda de `dedup`/`idempot`/`putIfAbsent` sin resultados). En el flujo batch estos adapters **ya** reciben `notification_id` como message id vía engine_nlp_ms, así que T-07 iguala el flujo online a un comportamiento que ya existe. |
| Productores online y `CorrelationId` (D-5) | ⏳ **Pendiente: requiere al equipo** | Ningún servicio del monorepo publica en `KAFKA-TOPIC-ONLINE-CAMPAIGN` (`#{segment}-online-campaign-kafka-topic-name`); solo platform_campaigns_ms lo consume. El productor es externo (la AsyncAPI dice `Source: <sistema origen de la notificación>`). Hay que preguntar quién publica y si envía `CorrelationId`. No bloquea: `TraceContext` (T-03) usa `notification_id` si el header falta o viene vacío. |

### Decisiones

Las recomendaciones técnicas se sostienen con la evidencia. La aprobación queda pendiente del equipo.

| Decisión | Recomendación | Estado |
|---|---|---|
| D-1 `metadata.Id` sigue siendo UUID | Mantener | ⏳ Pendiente de aprobación |
| D-2 `eventId` sigue siendo UUID | Mantener (engine_nlp_ms no usa `eventId`) | ⏳ Pendiente de aprobación |
| D-3 enviar `campaign_id` al engine | Sí; validado que no rompe | ⏳ Pendiente de aprobación |
| D-4 sin MDC en platform_campaigns_ms | Sí | ⏳ Pendiente de aprobación |
| D-6 corregir `NotificationEndpoint` en esta HU (T-16) | Sí: fallo confirmado; sin T-16 no hay reintentos ni traza de reintentos | ⏳ Pendiente de aprobación |

### Observación fuera del alcance

`IncomingEventValidator.validateChannel` de engine_nlp_ms solo acepta `"msteams"` y `"WhatsApp"` (con esa capitalización). platform_campaigns_ms reenvía `channel` tal como viene del CSV o del scheduler. Si una campaña de WhatsApp llega con `"whatsapp"` en minúsculas, engine_nlp_ms la rechazaría. **No se verificó** qué valor llega en producción; se deja como punto a revisar con el equipo.

## Criterios de terminado

- [x] Tabla de resultados completa (D-5 queda pendiente del equipo, no bloqueante).
- [x] Ningún bloqueante técnico para T-05, T-06 y T-07.
- [ ] Aprobación del equipo para D-1…D-4 y D-6.
- [ ] Ningún bloqueante abierto. Si hay uno, ajustar el plan y las tasks afectadas antes de seguir. Por ejemplo, si engine_nlp_ms rechaza `campaign_id`, en T-05 se envía solo en el header AMQP.
