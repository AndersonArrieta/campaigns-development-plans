# T-07 — platform_campaigns_ms: `MessageIdentifier = notification_id` en el flujo online

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-6, P-11
- **Depende de:** T-01 (validación de los adapters out), T-03

## Objetivo

Que el mensaje del flujo online hacia los adapters lleve `metadata.MessageIdentifier = notification_id` en lugar de un UUID aleatorio, y que `OnlineMessageUseCase` registre la traza completa.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/usecase/src/main/java/co/com/bancolombia/usecase/AdapterMessageUseCase.java` | Nuevo parámetro `messageId`. |
| `domain/usecase/src/main/java/co/com/bancolombia/usecase/OnlineMessageUseCase.java` | Usa `TraceContext` y pasa `data.notificationId()`. |
| `domain/usecase/src/test/java/.../OnlineMessageUseCaseTest.java` y la prueba de `AdapterMessageUseCase` (crearla si no existe) | Ajustar y ampliar. |

## Pasos

1. `AdapterMessageUseCase`:
   ```java
   public Mono<AdapterOutStatusResponse> sendMessageToAdapter(String appId, String chatter, String message,
                                                              String channel, String messageId)
   ```
   - `messageIdentifier(resolveMessageId(messageId))`: si `messageId` está vacío, usar `UUID.randomUUID()` y registrar un WARNING.
   - `metadata.id` sigue siendo `UUID.randomUUID()` (id del evento).
   - Buscar otros llamadores de `sendMessageToAdapter(` en `src/main` (por ahora solo `OnlineMessageUseCase`). Si aparecen, ajustarlos o mantener una sobrecarga de 4 parámetros que delegue con `null`.
2. `OnlineMessageUseCase`:
   - `TraceContext trace = TraceContext.from(data, headers);`
   - Firmas privadas con `TraceContext` y logs con `trace.toLog()`.
   - `adapterMessageUseCase.sendMessageToAdapter(data.appId(), data.user(), data.message(), data.channel(), data.notificationId())`.

## Pruebas

- `AdapterMessageUseCase`: capturar el `AdapterOutMessage` → `metadata().messageIdentifier() == notificationId`; `metadata().id()` sigue siendo un UUID válido y distinto; con `messageId` vacío → `messageIdentifier` es un UUID.
- `OnlineMessageUseCaseTest`: verificar que se llama `sendMessageToAdapter(..., notificationId)`; con headers `null` el flujo funciona.

## Criterios de terminado

- [x] T-01 confirmó que ningún adapter deduplica por `MessageIdentifier`.
- [x] `MessageIdentifier` = `notification_id` en el flujo online (si viene vacío se genera un UUID y se registra un WARNING).
- [x] Pruebas en verde: `usecase` 92 pruebas, 0 fallos; compila todo el proyecto. `AdapterMessageUseCase` y `OnlineMessageUseCase`: 100 % de líneas y ramas. Pitest: 13 mutantes eliminados; 1 sin cobertura en el `onErrorMap` del gateway (código previo, no modificado) (2026-10-08).
- [ ] Commit (lo hace el desarrollador).
