# `POST /api/v1/notifications`

Publica un evento de **notificación en línea** (texto ya construido) en el tópico Kafka `notifications` del segmento al que pertenece `data.applicationIdentifier`.

| Propiedad | Valor |
|---|---|
| Método | `POST` |
| Ruta | `/api/v1/notifications` |
| Handler | `Handler#handleNotificationRequest` |
| Caso de uso | `PublishNotificationUseCase` |
| Request DTO | `NotificationEventRequest` |
| Tópico | `segments_destinies.<segmento>.kafka.notifications` |
| Secreto | `segments_destinies.<segmento>.kafka.secret_campaigns` (el mismo de campañas) |
| Key del mensaje Kafka | `metadata.Id` |

## Headers

| Header | Requerido | Valor |
|---|---|---|
| `Content-Type` | Sí | `application/json` |
| `Accept` | No | `application/json` o `*/*`. Un valor incompatible produce `404`. |

No hay autenticación a nivel de aplicación en el endpoint.

## Request body

### Estructura

```
NotificationEventRequest
├── metadata (obligatorio)
│   ├── Id               string  obligatorio  → key del mensaje Kafka
│   ├── Source           string  obligatorio
│   ├── SpecVersion      string  obligatorio
│   ├── Type             string  obligatorio
│   ├── DataContentType  string  obligatorio
│   ├── DataSchema       string  obligatorio
│   └── Time             string  obligatorio
└── data (obligatorio)
    ├── userIdentifier         string  obligatorio
    ├── sourceChannel          string  obligatorio
    ├── applicationIdentifier  string  obligatorio  → define el segmento
    └── notification (obligatorio)
        ├── identifier      string               obligatorio
        ├── dataTime        string               obligatorio
        ├── message         string               obligatorio
        └── messageContext  object (clave/valor) opcional
```

### Campos

| Campo | Tipo | Oblig. | Mensaje de validación |
|---|---|---|---|
| `metadata` | object | Sí | `El objeto 'metadata' es obligatorio` |
| `metadata.Id` … `metadata.Time` | string | Sí | `El campo 'metadata.<Campo>' es obligatorio` (igual que en campañas) |
| `data` | object | Sí | `El objeto 'data' es obligatorio` |
| `data.userIdentifier` | string | Sí | `El campo 'data.userIdentifier' es obligatorio` |
| `data.sourceChannel` | string | Sí | `El campo 'data.sourceChannel' es obligatorio` |
| `data.applicationIdentifier` | string | Sí | `El campo 'data.applicationIdentifier' es obligatorio` |
| `data.notification` | object | Sí | `El objeto 'data.notification' es obligatorio` |
| `data.notification.identifier` | string | Sí | `El campo 'data.notification.identifier' es obligatorio` |
| `data.notification.dataTime` | string | Sí | `El campo 'data.notification.dataTime' es obligatorio` |
| `data.notification.message` | string | Sí | `El campo 'data.notification.message' es obligatorio` |
| `data.notification.messageContext` | object | No | — |

Las reglas generales (`@NotBlank`, PascalCase en `metadata`, campos desconocidos ignorados, una sola violación reportada) son las mismas que en [`/api/v1/campaigns`](POST-api-v1-campaigns.md#campos).

### Ejemplo

```json
{
  "metadata": {
    "Id": "msg-002",
    "Source": "mapper:whatsapp",
    "SpecVersion": "1.0.2",
    "Type": "notification.execute",
    "DataContentType": "application/json",
    "DataSchema": "https://schema-registry.com",
    "Time": "2026-10-21T14:15:22Z"
  },
  "data": {
    "userIdentifier": "573175324391",
    "sourceChannel": "WhatsApp",
    "applicationIdentifier": "performance_test",
    "notification": {
      "identifier": "notif-002",
      "dataTime": "2026-10-21 15:00:00",
      "message": "Tu solicitud fue procesada correctamente.",
      "messageContext": {}
    }
  }
}
```

## Respuestas

| HTTP | Cuándo | Body |
|---|---|---|
| `202 Accepted` | Kafka confirmó la escritura | `{"status": "accepted", "message": "Notification event accepted for Kafka publication"}` |
| `400 Bad Request` | Falla Bean Validation, o `applicationIdentifier` / `metadata.Id` vacíos en el caso de uso, o falla la serialización | `{"error": "<mensaje de validación>"}` |
| `422 Unprocessable Content` | No se pudo resolver el destino o el secreto (`IllegalStateException`) | `{"error": "<mensaje>"}` |
| `500 Internal Server Error` | JSON mal formado, `Content-Type` no soportado, fallo de DynamoDB, reintentos de Kafka agotados | `{"error": "Error tecnico al publicar la notificacion"}` |
| `404 Not Found` | `Accept` incompatible | Respuesta por defecto de Spring |

Los mensajes 422 son los mismos de [campañas](POST-api-v1-campaigns.md#mensajes-de-error-422-posibles), salvo:

- `No existe topico Kafka configurado para el segmento: <segmento>` → falta `kafka.notifications`.
- `No fue posible resolver el destino Kafka para notificaciones`.

## Mensaje publicado en Kafka

- **Key:** `metadata.Id`.
- **Value:** JSON de `NotificationEvent` (claves de `metadata` en camelCase, ver [observaciones](../observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)).

```json
{
  "metadata": {
    "id": "msg-002",
    "source": "mapper:whatsapp",
    "specVersion": "1.0.2",
    "type": "notification.execute",
    "dataContentType": "application/json",
    "dataSchema": "https://schema-registry.com",
    "time": "2026-10-21T14:15:22Z"
  },
  "data": {
    "userIdentifier": "573175324391",
    "sourceChannel": "WhatsApp",
    "applicationIdentifier": "performance_test",
    "notification": {
      "identifier": "notif-002",
      "dataTime": "2026-10-21 15:00:00",
      "message": "Tu solicitud fue procesada correctamente.",
      "messageContext": {}
    }
  }
}
```

El consumidor de este tópico es `platform_campaigns_ms` (tópico `...campaignmanagement.executenotificationv1` en sus docs).

## Ejemplo cURL

```bash
curl -i -X POST "http://localhost:8080/api/v1/notifications" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d @notification.json
```
