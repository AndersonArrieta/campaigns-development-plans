# Guía de pruebas

## Prerrequisitos

1. **Configuración de segmentos en DynamoDB** con el `appId` de prueba dentro de algún segmento y su bloque `kafka` completo (`campaigns`, `notifications`, `secret_campaigns`). Ver [publicacion-kafka.md](publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter).
2. **Secreto en Secrets Manager** con el nombre de `secret_campaigns` y las claves `username`, `password`, `bootstrapserver`.
3. **Tópicos creados** en el broker y permisos de escritura para el usuario del secreto.
4. Para ejecución local: perfil `local` (conexión `PLAINTEXT`, LocalStack en `http://localhost:4566`) y `spring.profiles.active` definido, porque `KafkaProducerConfig` lo inyecta sin valor por defecto.

## Casos de prueba

Base URL local: `http://localhost:8080`.

### `POST /api/v1/campaigns`

| # | Caso | Preparación / payload | Esperado |
|---|---|---|---|
| C-01 | Publicación exitosa | Payload válido, `appId` en segmento con Kafka configurado | `202`, `{"status":"accepted","message":"Campaign event accepted for Kafka publication"}`; mensaje en tópico `campaigns` con key = `metadata.Id` |
| C-02 | Solo campos obligatorios | Sin `retries`, `node`, `messageContext` | `202`; en Kafka esos campos llegan como `null` |
| C-03 | Falta `metadata` | Omitir `metadata` | `400`, `El objeto 'metadata' es obligatorio` |
| C-04 | `metadata.Id` en blanco | `"Id": "  "` | `400`, `El campo 'metadata.Id' es obligatorio` |
| C-05 | `metadata` en camelCase | `"id"` en vez de `"Id"` | `400`, `El campo 'metadata.Id' es obligatorio` (la clave se ignora) |
| C-06 | Falta `data.campaign` | Omitir `campaign` | `400`, `El objeto 'data.campaign' es obligatorio` |
| C-07 | Falta `notification.dataTime` | Omitir `dataTime` | `400`, `El campo 'data.campaign.notification.dataTime' es obligatorio` |
| C-08 | `appId` sin segmento | `applicationIdentifier: "no_existe"` | `422`, `No existe segmento configurado para applicationIdentifier: no_existe` |
| C-09 | Segmento sin `kafka.campaigns` | Quitar `campaigns` del segmento | `422`, `No existe topico Kafka configurado para el segmento: <seg>` |
| C-10 | Segmento sin `secret_campaigns` | Quitar el secreto | `422`, `No existe secretCampaigns configurado para el segmento: <seg>` |
| C-11 | Secreto inexistente en AWS | `secret_campaigns` con nombre inválido | `422`, `No fue posible obtener el secreto de Kafka: <secreto>`; health `DOWN` |
| C-12 | Broker inaccesible | `bootstrapserver` inválido | `500` tras varios reintentos (puede tardar > 1 min); health `DOWN` |
| C-13 | JSON mal formado | Body `{"metadata":` | `500`, `Error tecnico al publicar la campana` |
| C-14 | Body vacío | Sin body, `Content-Type: application/json` | `202` **sin publicar nada** (ver [observaciones](observaciones.md#2-body-vacío-responde-202-sin-publicar)) |
| C-15 | `Accept: text/plain` | Payload válido | `404` |
| C-16 | Campos extra | Agregar `"foo": "bar"` en cualquier nivel | `202`; el campo no viaja a Kafka |
| C-17 | `retries` numérico | `"retries": 3` | `202`; Jackson lo convierte a `"3"` |
| C-18 | Rotación de credenciales | Rotar password del secreto con el pod corriendo | Primer envío falla autenticación, se invalida cache y se reintenta: `202` |

### `POST /api/v1/notifications`

| # | Caso | Preparación / payload | Esperado |
|---|---|---|---|
| N-01 | Publicación exitosa | Payload válido | `202`, `{"status":"accepted","message":"Notification event accepted for Kafka publication"}`; mensaje en tópico `notifications` |
| N-02 | Falta `data.notification.message` | Omitir `message` | `400`, `El campo 'data.notification.message' es obligatorio` |
| N-03 | Falta `data.notification` | Omitir `notification` | `400`, `El objeto 'data.notification' es obligatorio` |
| N-04 | `appId` sin segmento | `applicationIdentifier: "no_existe"` | `422` |
| N-05 | Segmento sin `kafka.notifications` (pero con `campaigns`) | Quitar `notifications` | `422`, `No existe topico Kafka configurado para el segmento: <seg>`; `/api/v1/campaigns` sigue funcionando |
| N-06 | JSON mal formado | Body truncado | `500`, `Error tecnico al publicar la notificacion` |

### Health

| # | Caso | Esperado |
|---|---|---|
| H-01 | Arranque sin envíos | `GET /actuator/health` → componente Kafka `UNKNOWN`, detalle `Esperando primer envio a Kafka` |
| H-02 | Tras C-01 | Componente `UP` |
| H-03 | Tras C-12 | Componente `DOWN` con `reason`; `/actuator/health` responde `503` |

## Payloads

`campaign.json`:

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
        "messageContext": { "nombre": "Juan" }
      }
    }
  }
}
```

`notification.json`:

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
      "message": "Hola notificacion"
    }
  }
}
```

## Comandos

```bash
# Campaña
curl -i -X POST http://localhost:8080/api/v1/campaigns \
  -H "Content-Type: application/json" -d @campaign.json

# Notificación
curl -i -X POST http://localhost:8080/api/v1/notifications \
  -H "Content-Type: application/json" -d @notification.json

# Health
curl -s http://localhost:8080/actuator/health

# Verificar el mensaje en el tópico (broker local)
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic <tópico> --from-beginning --property print.key=true
```

## Pruebas unitarias de la rama

Desde `queuer_ms/`:

```bash
./gradlew test
```

Clases de prueba agregadas: `HandlerTest`, `RouterRestTest`, `PublishCampaignUseCaseTest`, `PublishNotificationUseCaseTest`, `SegmentRoutingAdapterTest`, `KafkaPublisherGatewayAdapterTest`, `KafkaProducerConfigTest`, `ResilientKafkaProducerTest`, `KafkaHealthIndicatorTest`, `KafkaSecretProviderTest`, `ReactiveCommonsConfigTest`.
