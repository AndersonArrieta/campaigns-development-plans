# T-03 — platform_campaigns_ms: `TraceContext` de dominio

- **Componente:** platform_campaigns_ms
- **Ítems del plan:** P-4
- **Depende de:** T-02

## Objetivo

Centralizar en un solo objeto cómo se resuelve la correlación (`correlationId` con fallback a `notificationId`, y `campaignId`) y el formato de los logs de trazabilidad.

## Archivos

| Archivo | Cambio |
|---|---|
| **Nuevo** `domain/usecase/src/main/java/co/com/bancolombia/usecase/trace/TraceContext.java` | Record + fábricas + `toLog()`. |
| **Nuevo** `domain/usecase/src/test/java/co/com/bancolombia/usecase/trace/TraceContextTest.java` | Pruebas unitarias. |

## Diseño propuesto

```java
@Log
public record TraceContext(String correlationId, String campaignId,
                           String notificationId, String appId) {

    public static TraceContext from(BatchEventData data, EventHeaders headers) {
        String notificationId = data != null ? data.notificationId() : null;
        return new TraceContext(
                resolveCorrelationId(headerCorrelation(headers), notificationId),
                firstNonBlank(headers != null ? headers.campaignId() : null,
                              data != null ? data.campaignId() : null),
                notificationId,
                data != null ? data.appId() : null);
    }

    public static TraceContext from(OnlineEventData data, EventHeaders headers) { /* igual, campaignId solo del header */ }

    public String toLog() {
        return "correlationId=" + correlationId + ", notificationId=" + notificationId
                + ", campaignId=" + campaignId + ", appId=" + appId;
    }

    // resolveCorrelationId: usa el header si no está vacío; si no, notificationId.
    // Si los dos existen y son distintos -> log WARNING (productor mal configurado), y se respeta el header.
}
```

> Respetar el estilo del módulo `usecase`: `@Log` (java.util.logging) y records con `@Builder` si aplica.

## Pruebas (`TraceContextTest`)

| Caso | Esperado |
|---|---|
| Header `CorrelationId` = notificationId | `correlationId == notificationId`, sin warning |
| Header ausente / `null` / vacío | `correlationId == notificationId` |
| `headers == null` | `correlationId == notificationId`, `campaignId` del body (batch) |
| Header distinto de notificationId | Se usa el header y se registra un warning |
| `campaign_id` en el header y en el body | Gana el header |
| `campaign_id` solo en el body | Se usa el body |
| `data == null` | No lanza excepción; los campos quedan en `null` |
| `toLog()` | Formato exacto `correlationId=..., notificationId=..., campaignId=..., appId=...` |

## Criterios de terminado

- [x] Clase y pruebas creadas. `TraceContext`: 100 % de líneas y ramas (JaCoCo, 30/30 ramas), 22/22 mutantes eliminados (pitest). Módulo `usecase`: 84 pruebas, 0 fallos (2026-10-08).
- [x] Todavía sin uso en los use cases (se integra en T-04 y T-07).
- [ ] Commit (lo hace el desarrollador).
