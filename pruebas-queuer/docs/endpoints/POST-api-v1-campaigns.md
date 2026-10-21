# `POST /api/v1/campaigns`

Publica un evento de **campaña masiva** en el tópico Kafka `campaigns` del segmento al que pertenece `data.applicationIdentifier`.

| Propiedad | Valor |
|---|---|
| Método | `POST` |
| Ruta | `/api/v1/campaigns` |
| Handler | `Handler#handleCampaignRequest` |
| Caso de uso | `PublishCampaignUseCase` |
| Request DTO | `CampaignEventRequest` |
| Tópico | `segments_destinies.<segmento>.kafka.campaigns` |
| Secreto | `segments_destinies.<segmento>.kafka.secret_campaigns` |
| Key del mensaje Kafka | `metadata.Id` |

## Headers

| Header | Requerido | Valor |
|---|---|---|
| `Content-Type` | Sí | `application/json` |
| `Accept` | No | `application/json` o `*/*`. Si se envía un valor no compatible con JSON (p. ej. `text/plain`) la ruta no coincide y se responde `404`. |

No hay autenticación a nivel de aplicación en el endpoint.

## Request body

### Estructura

```
CampaignEventRequest
├── metadata (obligatorio)
│   ├── Id               string  obligatorio  → se usa como key del mensaje Kafka
│   ├── Source           string  obligatorio
│   ├── SpecVersion      string  obligatorio
│   ├── Type             string  obligatorio
│   ├── DataContentType  string  obligatorio
│   ├── DataSchema       string  obligatorio
│   └── Time             string  obligatorio
└── data (obligatorio)
    ├── applicationIdentifier  string  obligatorio  → define el segmento
    ├── sourceChannel          string  obligatorio
    ├── userIdentifier         string  obligatorio
    └── campaign (obligatorio)
        ├── identifier   string  obligatorio
        ├── retries      string  opcional
        └── notification (obligatorio)
            ├── identifier      string               obligatorio
            ├── node            string               opcional
            ├── dataTime        string               obligatorio
            └── messageContext  object (clave/valor) opcional
```

### Campos

| Campo | Tipo | Oblig. | Mensaje de validación |
|---|---|---|---|
| `metadata` | object | Sí | `El objeto 'metadata' es obligatorio` |
| `metadata.Id` | string | Sí | `El campo 'metadata.Id' es obligatorio` |
| `metadata.Source` | string | Sí | `El campo 'metadata.Source' es obligatorio` |
| `metadata.SpecVersion` | string | Sí | `El campo 'metadata.SpecVersion' es obligatorio` |
| `metadata.Type` | string | Sí | `El campo 'metadata.Type' es obligatorio` |
| `metadata.DataContentType` | string | Sí | `El campo 'metadata.DataContentType' es obligatorio` |
| `metadata.DataSchema` | string | Sí | `El campo 'metadata.DataSchema' es obligatorio` |
| `metadata.Time` | string | Sí | `El campo 'metadata.Time' es obligatorio` |
| `data` | object | Sí | `El objeto 'data' es obligatorio` |
| `data.applicationIdentifier` | string | Sí | `El campo 'data.applicationIdentifier' es obligatorio` |
| `data.sourceChannel` | string | Sí | `El campo 'data.sourceChannel' es obligatorio` |
| `data.userIdentifier` | string | Sí | `El campo 'data.userIdentifier' es obligatorio` |
| `data.campaign` | object | Sí | `El objeto 'data.campaign' es obligatorio` |
| `data.campaign.identifier` | string | Sí | `El campo 'data.campaign.identifier' es obligatorio` |
| `data.campaign.retries` | string | No | — |
| `data.campaign.notification` | object | Sí | `El objeto 'data.campaign.notification' es obligatorio` |
| `data.campaign.notification.identifier` | string | Sí | `El campo 'data.campaign.notification.identifier' es obligatorio` |
| `data.campaign.notification.node` | string | No | — |
| `data.campaign.notification.dataTime` | string | Sí | `El campo 'data.campaign.notification.dataTime' es obligatorio` |
| `data.campaign.notification.messageContext` | object | No | — |

Reglas:

- Los campos `string` obligatorios usan `@NotBlank`: se rechazan `null`, `""` y cadenas solo con espacios.
- Las claves de `metadata` van en **PascalCase** (`Id`, `Source`, …); las de `data` en **camelCase**.
- Los campos desconocidos se ignoran (`@JsonIgnoreProperties(ignoreUnknown = true)`).
- No se valida el formato de `Time` ni de `dataTime`; son cadenas libres.
- Si hay varias violaciones, solo se devuelve **una** (la primera que reporta el validador, sin orden garantizado).

### Ejemplo

```json
{
  "metadata": {
    "Id": "msg-001",
    "Source": "platform:campaigns",
    "SpecVersion": "1.0.2",
    "Type": "initiatecampaign",
    "DataContentType": "application/json",
    "DataSchema": "https://schema-registry.com",
    "Time": "2026-10-21T14:15:22Z"
  },
  "data": {
    "applicationIdentifier": "performance_test",
    "sourceChannel": "WhatsApp",
    "userIdentifier": "573175324392",
    "campaign": {
      "identifier": "cmp-001",
      "retries": "3",
      "notification": {
        "identifier": "notif-001",
        "node": "N-00-00-02",
        "dataTime": "2026-10-21 15:00:00",
        "messageContext": {
          "nombre": "Juan",
          "producto": "Tarjeta"
        }
      }
    }
  }
}
```

## Respuestas

| HTTP | Cuándo | Body |
|---|---|---|
| `202 Accepted` | Kafka confirmó la escritura | `{"status": "accepted", "message": "Campaign event accepted for Kafka publication"}` |
| `400 Bad Request` | Falla Bean Validation, o el caso de uso detecta `applicationIdentifier` / `metadata.Id` vacíos, o el payload no se puede serializar | `{"error": "<mensaje de validación>"}` |
| `422 Unprocessable Content` | No se pudo resolver el destino Kafka o no se pudo obtener/usar el secreto (cualquier `IllegalStateException`) | `{"error": "<mensaje>"}` |
| `500 Internal Server Error` | Cualquier otro error: JSON mal formado, `Content-Type` no soportado, fallo de DynamoDB, reintentos de Kafka agotados | `{"error": "Error tecnico al publicar la campana"}` |
| `404 Not Found` | `Accept` incompatible con `application/json` | Respuesta por defecto de Spring |

### Mensajes de error 422 posibles

| Mensaje | Causa |
|---|---|
| `No existe segmento configurado para applicationIdentifier: <appId>` | El `appId` no está en ninguna lista de `segments` |
| `No existe segmentsDestinies en la configuracion` | La configuración no trae `segments_destinies` |
| `No existe configuracion Kafka para el segmento: <segmento>` | El segmento no tiene bloque `kafka` |
| `No existe topico Kafka configurado para el segmento: <segmento>` | Falta `kafka.campaigns` |
| `No existe secretCampaigns configurado para el segmento: <segmento>` | Falta `kafka.secret_campaigns` |
| `No fue posible resolver el destino Kafka para campanas` | El adaptador de enrutamiento devolvió vacío |
| `No fue posible obtener el secreto de Kafka: <secreto>` | Secrets Manager falló o el secreto no existe |
| `Kafka bootstrapserver no encontrado en el secreto` | El secreto no tiene `bootstrapserver` |
| `Credenciales Kafka no encontradas en el secreto para perfil no local` | Faltan `username`/`password` fuera del perfil `local` |

## Mensaje publicado en Kafka

- **Key:** valor de `metadata.Id` (string).
- **Value:** JSON del objeto de dominio `CampaignEvent` serializado con el `ObjectMapper` de Spring.

> **Atención:** el modelo de dominio no tiene `@JsonProperty`, así que las claves de `metadata` salen en **camelCase** (`id`, `source`, `specVersion`, …) y no en PascalCase como llegaron. Los campos opcionales ausentes salen como `null`. Ver [observaciones](../observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata).

```json
{
  "metadata": {
    "id": "msg-001",
    "source": "platform:campaigns",
    "specVersion": "1.0.2",
    "type": "initiatecampaign",
    "dataContentType": "application/json",
    "dataSchema": "https://schema-registry.com",
    "time": "2026-10-21T14:15:22Z"
  },
  "data": {
    "applicationIdentifier": "performance_test",
    "sourceChannel": "WhatsApp",
    "userIdentifier": "573175324392",
    "campaign": {
      "identifier": "cmp-001",
      "retries": "3",
      "notification": {
        "identifier": "notif-001",
        "node": "N-00-00-02",
        "dataTime": "2026-10-21 15:00:00",
        "messageContext": { "nombre": "Juan", "producto": "Tarjeta" }
      }
    }
  }
}
```

El consumidor de este tópico es `platform_campaigns_ms` (tópico `...campaignexecution.initiatecampaignv1` en sus docs).

## Ejemplo cURL

```bash
curl -i -X POST "http://localhost:8080/api/v1/campaigns" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d @campaign.json
```
