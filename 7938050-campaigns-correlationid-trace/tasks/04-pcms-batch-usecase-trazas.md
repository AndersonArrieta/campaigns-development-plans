# T-04 — platform_campaigns_ms: trazas en `BatchMessageUseCase`

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-5
- **Depende de:** T-03

## Objetivo

Que todos los logs del flujo batch (validación, reprogramación, envío al engine, error y rechazo) incluyan `correlationId` (nunca `null` si hay `notificationId`) y `campaignId`.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/usecase/src/main/java/co/com/bancolombia/usecase/BatchMessageUseCase.java` | Reemplazar `String correlationId` por `TraceContext`. |
| `domain/usecase/src/test/java/co/com/bancolombia/usecase/BatchMessageUseCaseTest.java` | Ajustar y ampliar. |

## Pasos

1. En `processMessage`:
   ```java
   BatchEventData data = message.data();
   TraceContext trace = TraceContext.from(data, headers);
   ```
2. Cambiar las firmas privadas para que reciban `TraceContext trace` en lugar de `String correlationId`:
   `scheduleOrSend`, `resolveSchedule`, `reschedule`, `sendToEngine`, `rejectInvalidMessage`.
3. Reescribir los mensajes de log para usar `trace.toLog()`:
   - `reschedule`: `"[batch_message_usecase] Campaña fuera del horario ({0}). Reprogramando para {1}."`
   - `sendToEngine` (INFO y SEVERE en `doOnError`).
   - `rejectInvalidMessage` (SEVERE con los errores de validación).
4. No cambiar la lógica funcional (cron, expiración, atributos de Dynamo).

## Pruebas

- Los casos existentes de `BatchMessageUseCaseTest` siguen en verde con el nuevo `EventHeaders(correlationId, campaignId)`.
- Nuevo: headers `null` → el flujo funciona igual (envío al engine o reprogramación) sin NPE.
- Nuevo (opcional): capturar el log con un `Handler` de JUL y verificar que contiene `correlationId=<notificationId>` y `campaignId=<campaignId>`.

## Criterios de terminado

- [x] Ningún log de `BatchMessageUseCase` usa todavía la variable `correlationId` suelta.
- [x] Pruebas en verde: `usecase` 88 pruebas, 0 fallos; compila todo el proyecto (`testClasses`). `BatchMessageUseCase`: 100 % de líneas, 20/21 mutantes eliminados. El que sobrevive está en `resolveCronExpression` (código previo, no modificado) (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
