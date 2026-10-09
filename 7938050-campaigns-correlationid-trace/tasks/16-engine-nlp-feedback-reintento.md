# T-16 — engine_nlp_ms: corregir el feedback de reintento a platform_campaigns_ms

- **Componente:** engine_nlp_ms
- **Ítems del plan:** §2.5, D-6
- **Depende de:** T-01 (evidencia del fallo y aprobación de D-6). Es independiente del resto y se puede hacer en paralelo.
- **Requerida por:** T-15, paso 6 (trazabilidad del ciclo de reintentos)

> ⚠️ Esta task está fuera de los 3 componentes originales de la HU. Ejecutarla solo si D-6 se aprueba; si no, moverla a una HU aparte.

## Objetivo

Que `NotificationEndpoint.notifyCampaignReschedule` envíe a `POST /v1/retry` un body que platform_campaigns_ms acepte (`RetryRequestDto`): `{"datetime": "yyyy-MM-dd HH:mm:ss", "notification_id": "<uuid>"}`, con el `datetime` **original** de la notificación (clave de Dynamo) y con logs de trazabilidad.

## Archivos

| Archivo | Cambio |
|---|---|
| `infrastructure/driven-adapters/config-loader/src/main/java/co/com/bancolombia/service/NotificationEndpoint.java` | DTO, `build()`, `datetime`, logs. |
| `.../config-loader/src/test/java/.../service/NotificationEndpointTest.java` | Verificar el body real. |
| `.../async-event-bus/.../rabbit/handler/QueueEventProcessor.java` | (Opcional) log al disparar el reintento. |

## Pasos

1. Reemplazar la clase interna por un record serializable con nombres explícitos:
   ```java
   record NotificationRequest(
           @JsonProperty("datetime") String datetime,
           @JsonProperty("notification_id") String notificationId) { }
   ```
2. Construir el body con el `datetime` del evento (es la clave de la tabla de campañas), no con `now()`:
   ```java
   .bodyValue(new NotificationRequest(event.getDatetime(), event.getNotificationId()))
   ```
   - Validar que `event.getDatetime()` llega en formato `yyyy-MM-dd HH:mm:ss`; platform_campaigns_ms lo envía tal cual desde `BatchEventData.dateTime()`.
   - Si `datetime` o `notificationId` son nulos o vacíos, registrar un error y no llamar al endpoint.
3. Trazabilidad:
   - `TraceLog.info(... "notifyCampaignReschedule:start" ...)` con `event.getMessageId()` (= `notification_id`) antes del POST.
   - `doOnSuccess` → `notifyCampaignReschedule:success`.
   - Agregar el status HTTP al log de error existente (`WebClientResponseException#getStatusCode`).
4. Revisar el validador `isEmpty()` sobre `feedbackUrl`: hoy lanza una excepción síncrona fuera del `Mono`. Si es `null`, se produce un NPE. Cambiarlo a `Mono.error(...)` con `isBlank()` y control de null.

## Pruebas (`NotificationEndpointTest`)

- Capturar el argumento de `bodyValue` y serializarlo con `ObjectMapper` →
  `{"datetime":"2026-10-08 10:00:00","notification_id":"<uuid>"}`.
- `datetime` o `notification_id` nulos → no se llama a `webClient.post()`.
- `feedbackUrl` nulo o vacío → `Mono.error(IllegalArgumentException)`, sin NPE.
- (Opcional, integración) `MockWebServer`: el request recibido tiene `Content-Type: application/json` y el body esperado.

## Criterios de terminado

- [ ] El body cumple el contrato de `RetryRequestDto` (snake_case y formato de `datetime`).
- [ ] Un `POST /v1/retry` real en dev responde 200 y `RetryUseCase` reprograma el ítem con `retries+1`.
- [ ] Logs de inicio, éxito y error con `traceId=<notification_id>`.
- [ ] Pruebas en verde y cobertura dentro del umbral de engine_nlp_ms.
