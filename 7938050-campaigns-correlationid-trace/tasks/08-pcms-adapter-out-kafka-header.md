# T-08 — platform_campaigns_ms: header `CorrelationId` en `AdapterOutKafkaService`

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-12
- **Depende de:** T-07

## Objetivo

Que el registro Kafka enviado a los topics adapter-out lleve el header `CorrelationId` y use `notification_id` como key.

## Archivos

| Archivo | Cambio |
|---|---|
| `infrastructure/driven-adapters/kafka-producer/src/main/java/co/com/bancolombia/events/AdapterOutKafkaService.java` | Header, key y log. |
| `infrastructure/driven-adapters/kafka-producer/src/test/java/co/com/bancolombia/events/AdapterOutKafkaServiceTest.java` | Crear o ampliar. |

## Pasos

1. Obtener el id de correlación:
   ```java
   String correlationId = message.metadata() != null ? message.metadata().messageIdentifier() : null;
   ```
2. Construir el `ProducerRecord` con key y header (reutilizar la constante `CORRELATION_ID` de `AbstractKafkaService`, que hoy no se usa):
   ```java
   ProducerRecord<String, String> pRecord =
           new ProducerRecord<>(topic, correlationId, mapper.writeValueAsString(messageDto));
   if (correlationId != null && !correlationId.isBlank()) {
       pRecord.headers().add(CORRELATION_ID, correlationId.getBytes(StandardCharsets.UTF_8));
   }
   ```
3. Cambiar el `log.debug` por un log con `topic` y `correlationId`.

## Pruebas

- Mockear `ResilientKafkaProducer.send` y capturar el `SenderRecord`:
  - `record.key() == notificationId`;
  - `record.headers().lastHeader("CorrelationId")` == notificationId.
- Canal no soportado: sigue lanzando `IllegalArgumentException`.
- `messageIdentifier == null`: se envía sin header y sin key, sin NPE.

## Criterios de terminado

- [x] Header `CorrelationId` y key presentes (= `MessageIdentifier`). Si `MessageIdentifier` está vacío o falta `metadata`, se envía sin key ni header.
- [x] Pruebas en verde: `kafka-producer` 28 pruebas, 0 fallos. `AdapterOutKafkaService`: 100 % de líneas y ramas, 10/10 mutantes eliminados (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
