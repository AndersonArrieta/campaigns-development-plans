# Plan 7938050 — Trazabilidad extremo a extremo de campañas con `notification_id`

- **Rama:** `feature/7938050-campaigns-correlationid-trace`
- **Repositorio:** `NU0284001_Artemis_Chatbots_Platform_MR`
- **Componentes:** `ingester_Lambda/`, `scheduler_Lambda/`, `platform_campaigns_ms/`
- **Fecha:** 2026-10-08

## 1. Objetivo

Usar `notification_id` como identificador de correlación único en todo el flujo de campañas:

```
ingester_Lambda ──(DynamoDB)──> scheduler_Lambda ──(Kafka)──> platform_campaigns_ms ──(RabbitMQ)──> engine_nlp_ms ──> adapters out
                                                                     └──(Kafka, flujo online)──> adapters out
```

Así un mismo valor sirve para buscar en los logs de todos los componentes y en la tabla de campañas. En concreto:

1. **scheduler_Lambda** envía en cada registro Kafka los headers `CorrelationId = notification_id` y `campaign_id`.
2. **platform_campaigns_ms** lee esos headers y registra `correlationId` y `campaignId` en todos sus logs. Si falta el header, usa `notificationId` del body.
3. **platform_campaigns_ms** envía `message_id = notification_id` al engine (RabbitMQ) y a los adapters (Kafka adapter-out).

## 2. Situación actual (hallazgos)

### 2.1 ingester_Lambda — origen de los identificadores

| Identificador | Dónde se genera | Observación |
|---|---|---|
| `campaign_id` | `src/controllers/processor.py:180` — `str(uuid.uuid4())`, uno por archivo CSV | Se guarda en cada registro (`src/models/notification.py:175`). |
| `notification_id` | `src/models/notification.py:162` — `str(uuid.uuid4())`, uno por usuario y fecha/hora | Es la clave de la tabla de campañas (`datetime` + `notification_id`). |

➡️ Los dos IDs ya se generan y se guardan. **No hace falta cambiar el contrato.** Solo faltan detalles de log (ver §3.1).

### 2.2 scheduler_Lambda — publicación a Kafka

- `src/models/scheduler_model.py:119`: `message_id = notification["notification_id"]` → se usa como `Id` del mensaje.
- `src/models/scheduler_model.py:66`: `metadata.Id = uuid4()`, un id de evento distinto en cada publicación.
- `src/classes/queue_class.py:290-292`: solo envía los headers `content_type` y `message_id`. La key Kafka es `notification_id`.
- **No envía el header `CorrelationId`** ni `campaign_id`. `campaign_id` solo va en el body (`data.campaign.identifier`).
- Los logs de publicación (`queue_class.py:316-332`) muestran el `Message Id`, pero no `campaign_id`.

### 2.3 platform_campaigns_ms — consumo y reenvío

| Punto | Estado actual | Problema |
|---|---|---|
| `kafka-consumer/.../dto/EventHeadersDto` | Solo mapea el header `CorrelationId` | El scheduler no lo envía, así que **`correlationId` siempre llega `null`**. |
| `model/event/EventHeaders` | Solo tiene `correlationId` | No hay `campaignId`. |
| `usecase/BatchMessageUseCase` | Registra `appId`, `notificationId` y `correlationId` | Falta `campaignId`. `correlationId` sale `null`. |
| `usecase/OnlineMessageUseCase` | Igual | Falta un fallback para `correlationId`. |
| `usecase/engine/EngineCampaignSenderUseCase` + `model/engine/EngineMessage` | Envía `notification_id`, pero no `message_id` | engine_nlp_ms lo compensa: si no llega `message_id`, usa `notification_id` (ver §2.4). La correlación depende de un fallback implícito del consumidor y no está declarada en el contrato. |
| `rabbit-publisher/EngineMessageSender` | `eventId = UUID.randomUUID()`. El único header AMQP es `x-consumer-id` | No hay header ni propiedad AMQP de correlación. |
| `usecase/AdapterMessageUseCase` (flujo online) | `messageIdentifier = UUID.randomUUID()` | Rompe la correlación: el adapter recibe un id que no existe en ningún otro componente. |
| `kafka-producer/AdapterOutKafkaService` | El `ProducerRecord` va sin headers. La constante `CORRELATION_ID` de `AbstractKafkaService` no se usa | No se propaga la correlación a los adapters. |
| `reactive-web/Handler` + `usecase/retry/RetryUseCase` | El reintento conserva `notificationId` | ✅ La correlación se mantiene entre reintentos. Falta registrarla en los logs. |
| `BatchMessageUseCase.reschedule` | Conserva `notificationId` y `campaign_id` en Dynamo | ✅ Sin cambios funcionales. |

### 2.4 Consumidores downstream (fuera del alcance, solo como contrato)

- **engine_nlp_ms** (Java, Reactor RabbitMQ). Todas las rutas son relativas a `engine_nlp_ms/infrastructure/`:
  - **Lectura del body.** `entry-points/async-event-bus/.../rabbit/handler/IncomingMessageParser.java` toma el payload de `data` y deserializa a `IncomingEventRequestDto`. En `withEventFieldsResolved`, **si `message_id` es `null`, usa `notification_id`**.
  - **Trazabilidad interna.** `EventProcessingContextFactory` crea el `TraceCollector` con `traceId` o, si falta, con `messageId`. `TraceLogEvent.of(fn, requestTree)` usa `requestTree.messageId()` como `traceId` del MDC (`config-loader/.../service/log/TraceMdcContext`). Sus logs `[MSG_TRACE]` / `TraceLog` **ya quedan con `traceId = notification_id`**. El `message_id` explícito de P-9 deja la correlación declarada en el contrato y elimina la dependencia de ese fallback. `message_id` debe ser igual a `notification_id`: si fuera distinto, ganaría el explícito.
  - **Campos desconocidos.** `IncomingMessageParser` lee con `FAIL_ON_UNKNOWN_PROPERTIES` **activado**, pero `IncomingEventRequestDto` e `IncomingRequestDto` tienen `@JsonIgnoreProperties(ignoreUnknown = true)`, que prevalece. `campaign_id` se ignora sin error (**verificado en T-01**).
  - **Validación de notificaciones.** `IncomingEventValidator.validateNotification` exige `notification_id`, `notification_node` y `feedback_url` (este último debe estar en la lista `events.feedback_urls`). Para `event_type=notification` no valida `x-consumer-id` ni lee headers AMQP. Los headers nuevos (`CorrelationId`, `campaign_id`) se ignoran.
  - **`correlational_id`.** `IncomingRequestDto` tiene `@JsonProperty("correlational_id")`, pero el modelo intermedio `rabbit/model/EngineMessage` no lo tiene. Por eso `RequestTree.traceId` llega `null` por la vía RabbitMQ. **No sirve enviarlo** desde platform_campaigns_ms: la correlación debe ir en `message_id`.
  - **Salida hacia los adapters.** `OutboundEngineResponseMapper` copia `message_id` en `OutboundEngineResponse` (hacia adapter_gateway_ms / mapper_out del canal). En el flujo batch, el `notification_id` **llega a los adapters a través del engine** sin cambios. `EngineMessagePublisher.rabbitProperties()` no envía headers de correlación AMQP (mejora opcional, fuera del alcance).
- **whatsapp_adapter_out_ms / teams_adapter_out_ms** ya leen `metadata.MessageIdentifier` (`MetadataDto.messageId`). Cambiar su valor a `notification_id` no rompe el contrato.

### 2.5 Hallazgo crítico: feedback de reintento de engine_nlp_ms → platform_campaigns_ms

`engine_nlp_ms/infrastructure/driven-adapters/config-loader/.../service/NotificationEndpoint.notifyCampaignReschedule` se dispara solo ante `NullSessionException` (`QueueEventProcessor.handleNullSession`). **Confirmado en T-01** con el código real (ver `evidencias/t01/`): engine_nlp_ms serializa y envía `{}` sin error de serialización. platform_campaigns_ms lo rechaza con 400 (se deduce de `Handler.isValidPayload`), y en engine_nlp_ms eso solo queda como un log `notifyCampaignReschedule:error`. **Los reintentos por `NullSessionException` nunca se reprograman.**

| # | Problema | Efecto en `POST /v1/retry` de platform_campaigns_ms |
|---|---|---|
| 1 | `.bodyValue(NotificationRequest.builder()...datetime(...))` envía el **builder**, sin `.build()`. | El encoder Jackson 3 de WebClient (Spring 7) serializa el builder como **`{}`** sin lanzar error (verificado). |
| 2 | `NotificationRequest` tiene campos package-private sin getters ni `@JsonProperty`. | Aunque se hiciera `build()`, se serializaría `{}`, o bien `notificationId` en camelCase, cuando `RetryRequestDto` espera `notification_id`. |
| 3 | `datetime = ZonedDateTime.now().toString()` (ISO con zona). | `Handler.isValidPayload` exige `yyyy-MM-dd HH:mm:ss` → **400 Bad Request**. Además, `RetryUseCase` usa `datetime` como clave de Dynamo junto con `notification_id`: debería ser el `datetime` original del evento (`event.getDatetime()`), no la hora actual. |
| 4 | El error solo se registra en `doOnError` y la llamada se suscribe con `.subscribe()` (fire-and-forget). | Una falla no interrumpe el flujo y pasa desapercibida. |

➡️ La correlación del ciclo de reintentos (criterio de aceptación §9) **depende de corregir esto en engine_nlp_ms**, que no está entre los componentes de esta HU. Ver la decisión **D-6** y la task **T-16**.
- **whatsapp_adapter_out_ms / teams_adapter_out_ms** ya leen `metadata.MessageIdentifier` (`MetadataDto.messageId`). Cambiar su valor a `notification_id` no rompe el contrato.

## 3. Cambios propuestos

### 3.1 ingester_Lambda (bajo impacto, solo observabilidad)

| # | Archivo | Cambio |
|---|---|---|
| I-1 | `src/controllers/processor.py` | Al final del procesamiento, registrar `campaign_id`, `app_id`, `file_route` y el total de `notification_id` generados. |
| I-2 | `src/models/notification.py` (`_add_to_list`) | Log en DEBUG por cada registro: `[Campaign {campaign_id}] notification_id={id} datetime={datetime}`. Así se puede rastrear desde el origen sin saturar los logs INFO. |
| I-3 | Pruebas `test/src/models/test_notification.py` | Comprobar que cada registro tiene un `notification_id` UUID distinto y que todos comparten `campaign_id`. |

> No se cambia el esquema de DynamoDB ni el formato del CSV.

### 3.2 scheduler_Lambda

| # | Archivo | Cambio |
|---|---|---|
| S-1 | `src/models/scheduler_model.py` → `format_records` (l. 118-128) | Agregar `"campaign_id": notification["campaign_id"]` al dict del mensaje, junto a `Id`, `app_id` y `has_context`. |
| S-2 | `src/classes/queue_class.py` → `send_messages` (l. 290-292) | Construir los headers así:<br>`content_type`, `message_id` (se mantiene por compatibilidad), **`CorrelationId` = notification_id**, **`campaign_id`** (si existe). Todos como `bytes` UTF-8. La key Kafka sigue siendo `notification_id`. |
| S-3 | `src/classes/queue_class.py` (logs l. 304-332) | Agregar `Campaign Id` y `Correlation Id` a los logs de éxito y error. Guardar `campaign_id` en la tupla `pending`. |
| S-4 | `src/models/scheduler_model.py` → `build_delivery_plan` (l. 246) | Agregar `campaign_id` al warning de mensajes descartados. |
| S-5 | `src/models/scheduler_model.py` → `build_event_message` | **Sin cambios de contrato.** `metadata.Id` sigue siendo un UUID por publicación (id de evento CloudEvents). La correlación va en el header. Ver la decisión D-1. |
| S-6 | Pruebas `test/src/classes/test_queue_class.py` y `test/src/models/test_scheduler_model.py` | Comprobar los headers enviados (`CorrelationId == notification_id`, `campaign_id`, `message_id`) y que `campaign_id` está en los mensajes formateados. |
| S-7 | `docs/docs/asyncapi.yaml` | Documentar los headers `CorrelationId` y `campaign_id` del mensaje publicado. |

Ejemplo de headers resultantes:

```python
headers = [
    ("content_type", b"application/json"),
    ("message_id", notification_id.encode("utf-8")),
    ("CorrelationId", notification_id.encode("utf-8")),
    ("campaign_id", campaign_id.encode("utf-8")),
]
```

> ⚠️ El nombre del header debe ser exactamente `CorrelationId`: es el `@JsonProperty` de `EventHeadersDto`, y `KafkaConsumer.parseHeaders` + `objectMapper.convertValue` diferencian mayúsculas.

### 3.3 platform_campaigns_ms

#### 3.3.1 Entrada (Kafka consumer)

| # | Archivo | Cambio |
|---|---|---|
| P-1 | `domain/model/.../event/EventHeaders.java` | Agregar el campo `String campaignId`. |
| P-2 | `infrastructure/entry-points/kafka-consumer/.../dto/EventHeadersDto.java` | Agregar `@JsonProperty("campaign_id") String campaignId`. Verificar que el `ObjectMapper` ignora los headers desconocidos (`content_type`, `message_id`); ya se cumple hoy, pero hay que cubrirlo con una prueba. |
| P-3 | `kafka-consumer/.../mappers/KafkaBatchEventMapper` y `KafkaOnlineEventMapper` | MapStruct mapea `campaignId` solo porque los nombres coinciden. Validar con una prueba del mapper. |

#### 3.3.2 Resolución de la correlación (dominio)

| # | Archivo | Cambio |
|---|---|---|
| P-4 | **Nuevo** `domain/usecase/.../usecase/trace/TraceContext.java` (record) | `record TraceContext(String correlationId, String campaignId, String notificationId, String appId)` con una fábrica:<br>• `correlationId` = header `CorrelationId` si no está vacío; si no, `data.notificationId()`.<br>• `campaignId` = header `campaign_id` si no está vacío; si no, `data.campaignId()` (solo batch).<br>• Si el header y `notificationId` no coinciden, log WARNING (ayuda a detectar productores mal configurados).<br>• `toLog()` → `correlationId=..., notificationId=..., campaignId=..., appId=...` para un formato uniforme. |
| P-5 | `domain/usecase/.../BatchMessageUseCase.java` | Reemplazar `String correlationId` por `TraceContext` en `scheduleOrSend`, `resolveSchedule`, `reschedule`, `sendToEngine` y `rejectInvalidMessage`. Todos los logs usan `trace.toLog()`, así que `campaignId` aparece en todos. Pasar `trace` a `engineCampaignSenderUseCase`. |
| P-6 | `domain/usecase/.../OnlineMessageUseCase.java` | Lo mismo con `TraceContext` (`campaignId` = null). Pasar `data.notificationId()` a `AdapterMessageUseCase`. |

#### 3.3.3 Salida hacia el engine (RabbitMQ)

| # | Archivo | Cambio |
|---|---|---|
| P-7 | `domain/model/.../engine/EngineMessage.java` | Agregar `String messageId` y `String campaignId`. |
| P-8 | `domain/usecase/.../engine/EngineCampaignSenderUseCase.java` → `buildEngineMessage` | `.messageId(campaignMessage.notificationId())` y `.campaignId(campaignMessage.campaignId())`. Log INFO antes de enviar, con `trace.toLog()`, `exchange` y `routingKey`. |
| P-9 | `infrastructure/driven-adapters/rabbit-publisher/.../dto/EngineMessageDto.java` | Agregar `@JsonProperty("message_id") String messageId` y `@JsonProperty("campaign_id") String campaignId`. El `EngineMapper` los mapea por nombre. |
| P-10 | `rabbit-publisher/.../EngineMessageSender.java` | • Headers AMQP: agregar `CorrelationId = message.getMessageId()` y `campaign_id`, manteniendo `x-consumer-id`.<br>• `BasicProperties`: `.messageId(messageId)` y `.correlationId(messageId)`.<br>• `eventId` del wrapper: sigue siendo UUID (ver D-2).<br>• Agregar `messageId` y `campaignId` al log `[engine_sender]`. |

Body resultante hacia el engine:

```json
{
  "eventId": "<uuid evento>",
  "name": "<routingKey>",
  "data": {
    "event_type": "notification",
    "message_id": "<notification_id>",
    "notification_id": "<notification_id>",
    "campaign_id": "<campaign_id>",
    "app_id": "...", "datetime": "...", "user_id": "...", "channel": "...",
    "notification_node": "...", "feedback_url": "...", "context": {}
  }
}
```

#### 3.3.4 Salida hacia los adapters (Kafka adapter-out, flujo online)

| # | Archivo | Cambio |
|---|---|---|
| P-11 | `domain/usecase/.../AdapterMessageUseCase.java` | Nueva firma `sendMessageToAdapter(appId, chatter, message, channel, messageId)`. `messageIdentifier(messageId)` usa `notificationId`. Si `messageId` está vacío, se usa un UUID como respaldo y se registra un warning. `metadata.id` sigue siendo un UUID por evento. |
| P-12 | `infrastructure/driven-adapters/kafka-producer/.../AdapterOutKafkaService.java` | Agregar al `ProducerRecord` el header `CorrelationId` (constante `CORRELATION_ID` que ya existe en `AbstractKafkaService`) con el valor `message.metadata().messageIdentifier()`. Usar `messageIdentifier` como key del registro para conservar el orden por notificación. Log con `topic` y `messageIdentifier`. |

#### 3.3.5 Reintentos (feedback del engine)

| # | Archivo | Cambio |
|---|---|---|
| P-13 | `infrastructure/entry-points/reactive-web/.../Handler.java` | Log INFO al recibir `/v1/retry`: `correlationId=<notification_id>, datetime=...`. |
| P-14 | `domain/usecase/.../retry/RetryUseCase.java` | Registrar `correlationId=notificationId`, `campaignId` (de `attributes["campaign_id"]`), `retries` y la nueva `datetime` al reprogramar o al llegar al máximo de reintentos. Sin cambios funcionales: `notificationId` se conserva y el scheduler lo vuelve a emitir con el mismo `CorrelationId`. |

#### 3.3.6 Documentación

| # | Archivo | Cambio |
|---|---|---|
| P-15 | `docs/docs/asyncapi.yaml` | • `EventHeaders`: agregar `campaign_id` y describir `CorrelationId = notification_id`.<br>• `AdapterOutMetadata.MessageIdentifier`: cambiar "UUID aleatorio" por "`notification_id` de la notificación".<br>• `EngineCampaignMessage`: agregar `message_id` y `campaign_id`, y los headers AMQP. |
| P-16 | `docs/docs/SequenceDiagrams.md` / `Functionalities.md` | Agregar una sección de trazabilidad con el diagrama del §1 y la tabla de identificadores (§4). |

## 4. Matriz final de identificadores

| Salto | Transporte | `notification_id` viaja como | `campaign_id` viaja como |
|---|---|---|---|
| ingester → Dynamo | DynamoDB | atributo `notification_id` (SK) | atributo `campaign_id` |
| scheduler → platform_campaigns_ms | Kafka | key, header `CorrelationId`, header `message_id`, `data.campaign.notification.identifier` | header `campaign_id`, `data.campaign.identifier` |
| platform_campaigns_ms → engine | RabbitMQ | `data.message_id`, `data.notification_id`, header `CorrelationId`, props `messageId`/`correlationId` | `data.campaign_id`, header `campaign_id` |
| engine_nlp_ms (logs internos) | MDC | `traceId` = `message_id` (= `notification_id`) | — (se ignora) |
| engine_nlp_ms → adapter_gateway / mapper_out (batch) | RabbitMQ / REST | `message_id` en `OutboundEngineResponse` | — |
| engine_nlp_ms → platform_campaigns_ms (retry) | HTTP | body `notification_id` (**requiere T-16**) | (se obtiene del ítem en Dynamo) |
| platform_campaigns_ms → adapter out (online) | Kafka | key, header `CorrelationId`, `metadata.MessageIdentifier` | — |

## 5. Decisiones a validar con el equipo

| ID | Decisión | Propuesta |
|---|---|---|
| D-1 | ¿`metadata.Id` del evento Kafka del scheduler debe ser igual a `notification_id`? | **No.** Se mantiene un UUID por publicación (semántica CloudEvents: id único del evento). La correlación va en `CorrelationId`. |
| D-2 | ¿`eventId` del wrapper RabbitMQ debe ser igual a `notification_id`? | **No**, por la misma razón. Un reintento produce un evento nuevo con el mismo `message_id`. |
| D-3 | ¿Enviar `campaign_id` al engine si hoy no lo usa? | **Sí.** Es aditivo, engine_nlp_ms lo ignora (`@JsonIgnoreProperties(ignoreUnknown = true)`; validarlo en T-01) y queda disponible para métricas futuras. |
| D-4 | ¿Usar MDC/Reactor Context en lugar de campos explícitos en los logs? | **Fuera del alcance.** El dominio usa `java.util.logging` (`@Log`) y el flujo es reactivo; los campos explícitos con `TraceContext.toLog()` son más simples y suficientes. Se puede evaluar en una historia aparte. |
| D-5 | ¿Algún otro productor del topic online envía `CorrelationId` distinto de `notification_id`? | Confirmar con los productores. Si es así, se respeta el header y solo se registra el warning de P-4. |
| D-6 | ¿Se corrige `NotificationEndpoint` de engine_nlp_ms (§2.5) dentro de esta HU? | **Sí, como task acotada (T-16)** en engine_nlp_ms. Sin ella, el criterio "trazabilidad incluyendo reintentos" no se puede cumplir. Si el equipo prefiere una HU aparte, ese criterio de §9 queda condicionado a ella. |

## 6. Plan de pruebas

### Unitarias

- **scheduler_Lambda:** headers enviados por `send_messages` (mock de `KafkaProducer.send`), `campaign_id` en `format_records` y logs con `campaign_id`.
- **ingester_Lambda:** unicidad de `notification_id` y `campaign_id` compartido.
- **platform_campaigns_ms:**
  - `TraceContextTest`: header presente, header vacío (fallback), headers `null`, header distinto (warning).
  - `KafkaBatchEventMapperTest` / `KafkaOnlineEventMapperTest`: mapeo de `campaign_id`.
  - `BatchMessageHandlerTest`: headers extra (`content_type`, `message_id`) no rompen la deserialización.
  - `BatchMessageUseCaseTest`: `EngineCampaignSenderUseCase` recibe un `EngineMessage` con `messageId == notificationId`.
  - `EngineCampaignSenderUseCaseTest` / `EngineMapperTest`: `message_id` y `campaign_id` en el DTO.
  - `EngineMessageSenderTest`: headers AMQP `CorrelationId`, `campaign_id`, `x-consumer-id` y las props `messageId`/`correlationId`.
  - `OnlineMessageUseCaseTest` / `AdapterMessageUseCase`: `messageIdentifier == notificationId` y el fallback a UUID.
  - `AdapterOutKafkaService`: header `CorrelationId` y key del registro.
  - `AdapterOutMapperTest`: sin cambios de forma.
- Cobertura ≥ el umbral actual del pipeline (Sonar).

### Integración / aceptación (ambiente dev)

1. Cargar un CSV de prueba con el ingester y anotar `campaign_id` y algunos `notification_id` en Dynamo.
2. Ejecutar el scheduler y verificar en CloudWatch: `Correlation Id` = `notification_id` y `Campaign Id`.
3. platform_campaigns_ms: logs `[batch_message_usecase] ... correlationId=<notification_id>, campaignId=<campaign_id>` (ya no `null`).
4. engine_nlp_ms: logs `[QueueHandler]`, `QueueEventProcessor:received` y `[MSG_TRACE]` con `traceId=<notification_id>` (MDC), y `OutboundEngineResponse.message_id=<notification_id>`.
5. Forzar un reintento (`NullSessionException`: usuario sin sesión o conversación) y verificar que llega a `POST /v1/retry` y que el nuevo ciclo mantiene el mismo `notification_id` (requiere T-16).
6. Flujo online: `MessageIdentifier` en el adapter-out = `notification_id`.
7. Consulta de punta a punta en el agregador de logs filtrando por un solo `notification_id`.

## 7. Orden de implementación y despliegue

Los cambios son **aditivos y compatibles hacia atrás**: platform_campaigns_ms tolera la ausencia de headers gracias al fallback, y el engine y los adapters ignoran los campos nuevos o ya los soportan.

1. **platform_campaigns_ms** (P-1 … P-16). Primero, para que lea `campaign_id` y haga el fallback antes de que llegue el header.
2. **scheduler_Lambda** (S-1 … S-7).
3. **ingester_Lambda** (I-1 … I-3). Solo logs, se puede desplegar en paralelo.
4. **engine_nlp_ms** (T-16, sujeto a D-6): corrección del feedback de reintento. Es independiente y se puede hacer en paralelo, pero debe estar en dev antes de validar los reintentos.
5. Validación de punta a punta en dev (§6), luego QA y PDN.

## 8. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Diferencia de mayúsculas en el nombre del header (`CorrelationId` vs `correlationId`). | Constante compartida y documentada. Prueba de `BatchMessageHandler` con un header real. |
| ~~Algún consumidor del adapter-out deduplica por `MessageIdentifier`~~ | **Descartado en T-01:** whatsapp/teams adapter out y webchat_mapper_out no deduplican. En el flujo batch ya reciben `notification_id` como message id vía engine_nlp_ms. |
| ~~engine_nlp_ms rechaza el body por `campaign_id`~~ | **Descartado en T-01:** la anotación `ignoreUnknown` del DTO prevalece. |
| Confusión con el header de request-reply de reactive-commons (`x-correlation-id`). | Usar exactamente `CorrelationId` (P-10). Verificado en T-01 que reactive-commons no usa las props AMQP `correlationId`/`messageId` en `listenQueue`. |
| El ciclo de reintentos no se puede trazar porque falla el feedback de engine_nlp_ms (§2.5). | T-16 (D-6). |
| Más volumen de logs. | Detalle por registro en DEBUG (ingester). En los demás componentes solo se agregan campos a logs que ya existen. |
| Los headers Kafka cuentan para el tamaño del mensaje. | Son ~80 bytes extra por registro; despreciable frente al body. |

## 9. Criterios de aceptación

- [ ] Todo mensaje del scheduler lleva los headers `CorrelationId = notification_id` y `campaign_id`.
- [ ] platform_campaigns_ms registra `correlationId` (nunca `null` si hay `notificationId`) y `campaignId` en cada log del flujo batch, online y de reintentos.
- [ ] El mensaje al engine tiene `data.message_id = notification_id` y los headers AMQP de correlación.
- [ ] El mensaje al adapter-out tiene `metadata.MessageIdentifier = notification_id` y el header `CorrelationId`.
- [ ] Con un solo `notification_id` se reconstruye el recorrido completo en los logs (ingester → scheduler → campaigns → engine → adapter, incluidos los reintentos).
- [ ] Pruebas unitarias en verde y cobertura dentro del umbral.
- [ ] AsyncAPI y documentación actualizadas.
