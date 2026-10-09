# T-02 — platform_campaigns_ms: headers de entrada `campaign_id`

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-1, P-2, P-3
- **Depende de:** —

## Objetivo

Que el consumidor Kafka lea, además de `CorrelationId`, el header `campaign_id` y lo deje en el modelo de dominio `EventHeaders`.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/model/src/main/java/co/com/bancolombia/model/event/EventHeaders.java` | Agregar `String campaignId`. |
| `infrastructure/entry-points/kafka-consumer/src/main/java/co/com/bancolombia/kafka/consumer/dto/EventHeadersDto.java` | Agregar `@JsonProperty("campaign_id") String campaignId`. |
| `.../kafka-consumer/.../mappers/KafkaBatchEventMapper.java` | Sin cambio de código; MapStruct mapea por nombre. Validarlo con una prueba. |
| `.../kafka-consumer/.../mappers/KafkaOnlineEventMapper.java` | Igual. |

## Pasos

1. Modificar el record de dominio:
   ```java
   @Builder(toBuilder = true)
   public record EventHeaders(
       String correlationId,
       String campaignId
   ) { }
   ```
2. Modificar el DTO:
   ```java
   public record EventHeadersDto(
       @JsonProperty("CorrelationId") String correlationId,
       @JsonProperty("campaign_id") String campaignId
   ) { }
   ```
3. Revisar todos los usos de `EventHeaders.builder()` / `new EventHeaders(...)` en `src/main` y `src/test`, y ajustarlos al nuevo constructor.
4. Confirmar que el `ObjectMapper` que usan `BatchMessageHandler` y `OnlineMessageHandler` ignora propiedades desconocidas (`content_type`, `message_id`). Si no, anotar el DTO con `@JsonIgnoreProperties(ignoreUnknown = true)`.

## Pruebas

- `KafkaBatchEventMapperTest` / `KafkaOnlineEventMapperTest`: `EventHeadersDto("corr", "camp")` → `EventHeaders` con los dos campos.
- `BatchMessageHandlerTest`: con los headers `{ "CorrelationId": "...", "campaign_id": "...", "content_type": "application/json", "message_id": "..." }`, el use case recibe `EventHeaders` con `correlationId` y `campaignId`, sin errores de deserialización.
- `OnlineMessageHandlerTest`: si falta `campaign_id`, `campaignId == null`.

## Criterios de terminado

- [x] Compila.
- [x] Pruebas nuevas y existentes en verde: 364 pruebas en 13 módulos, 0 fallos (2026-10-08).
- [x] No cambia el comportamiento funcional.
- [ ] Commit (lo hace el desarrollador).
