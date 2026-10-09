# T-09 — platform_campaigns_ms: trazas en el flujo de reintentos

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-13, P-14
- **Depende de:** — (se puede hacer en paralelo)

## Objetivo

Que el feedback del engine (`POST /v1/retry`) y la reprogramación queden registrados con `correlationId = notification_id` y `campaignId`, para unir los ciclos de reintento a la misma traza.

## Archivos

| Archivo | Cambio |
|---|---|
| `infrastructure/entry-points/reactive-web/src/main/java/co/com/bancolombia/api/Handler.java` | Log al recibir el request y al rechazarlo. |
| `domain/usecase/src/main/java/co/com/bancolombia/usecase/retry/RetryUseCase.java` | Logs de reprogramación, de máximo de reintentos y de ítem no encontrado. |
| Pruebas: `HandlerTest.java`, `RetryUseCaseTest.java` | Ajustar si aplica. |

## Pasos

1. `Handler.listenPOSTRetry`:
   - INFO al recibir un payload válido: `[retry_handler] Reintento recibido correlationId={notificationId}, datetime={datetime}`.
   - WARN si el payload es inválido (sin imprimir el body completo).
   - Agregar `correlationId` al log de error existente.
2. `RetryUseCase`:
   - Helper `traceOf(Notification item)` → `correlationId=<notificationId>, campaignId=<attributes.campaign_id>, appId=..., retries=...`.
   - INFO después de reprogramar: incluir la nueva `datetime`, `retries` y `expirationDate`.
   - El WARNING de "máximo número de reintentos" usa la traza en lugar de `item.toString()`.
   - Si `getItem` devuelve vacío, log WARN `Notificación no encontrada correlationId=...` (hoy termina en silencio).
3. Sin cambios funcionales.

## Pruebas

- Las pruebas existentes siguen en verde.
- Nuevo caso en `RetryUseCaseTest`: ítem inexistente → completa sin error (verificar que no llama a `createItem`).

## Criterios de terminado

- [x] Cada camino del reintento registra `correlationId`: recibido, rechazado con 400 (solo el motivo, sin valores recibidos), error al reprogramar, reprogramado, máximo de reintentos y no encontrado.
- [x] Pruebas en verde: `usecase` 95 y `reactive-web` 10 pruebas, 0 fallos. `RetryUseCase` 29/29 y `Handler` 14/14 mutantes eliminados (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
