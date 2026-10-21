# Guía de pruebas

## Prerrequisitos

1. **Configuración de segmentos en DynamoDB** con el `appId` de prueba dentro de algún segmento y su bloque `kafka` completo (`campaigns`, `notifications`, `secret_campaigns`). Ver [publicacion-kafka.md](publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter).
2. **Secreto en Secrets Manager** con el nombre de `secret_campaigns` y las claves `username`, `password`, `bootstrapserver`.
3. **Tópicos creados** en el broker y permisos de escritura para el usuario del secreto.
4. Para ejecución local: perfil `local` (conexión `PLAINTEXT`, LocalStack en `http://localhost:4566`) y `spring.profiles.active` definido, porque `KafkaProducerConfig` lo inyecta sin valor por defecto.

## Datos de prueba en dev

Se definen en [T-003](../backlog/tasks/T-003-datos-prueba-kafka-dev.md). Hasta que esa tarjeta se cierre, estos valores son propuestas:

| Dato | Valor | Estado |
|---|---|---|
| `kafkaAppId` (escenarios `202`) | `others-test` | Propuesto, por confirmar segmento y consumidor |
| `userIdentifier` ficticio | `573000000000` | Propuesto |
| `appId` sin segmento (escenarios `422`) | `queuer-acceptance-sin-segmento` | Propuesto, por verificar que no exista |

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

## Automatización en Karate

Escenarios que se agregan a las pruebas de despliegue de `queuer_ms`. El trabajo está planificado en el [backlog](../backlog/README.md); [T-007](../backlog/tasks/T-007-evidencias-y-trazabilidad.md) actualiza la columna de estado al ejecutarlos en `dev`.

### Aceptación — `queuer_ms/deployment/acceptanceTest`

| Escenario | Caso | Esperado | Tarjeta | Estado |
|---|---|---|---|---|
| AC-C01 | C-01 | `202` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C02 | C-02 | `202` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C03 | C-03 | `400` sin `metadata` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C04 | C-04 | `400` `metadata.Id` en blanco | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C05 | — | `400` sin `data.applicationIdentifier` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C06 | C-06 | `400` sin `data.campaign` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C07 | C-07 | `400` sin `notification.dataTime` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C08 | C-05 | `400` `metadata` en camelCase | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C09 | C-08 | `422` appId sin segmento | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-C10 | — | `403` RBAC | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Planeado |
| AC-N01 | N-01 | `202` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N02 | — | `202` sin `messageContext` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N03 | — | `400` sin `metadata` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N04 | — | `400` `metadata.Id` en blanco | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N05 | N-03 | `400` sin `data.notification` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N06 | N-02 | `400` sin `message` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N07 | — | `400` sin `userIdentifier` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N08 | N-04 | `422` appId sin segmento | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |
| AC-N09 | — | `403` RBAC | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Planeado |

### Humo — `queuer_ms/deployment/smokeTest`

| Escenario | Request | Esperado | Tarjeta | Estado |
|---|---|---|---|---|
| SM-01 | `GET /actuator/health` (existente) | `200` `UP` | — | Existente |
| SM-02 | `POST /api/v1/campaigns` sin `metadata` | `400` | [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md) | Planeado |
| SM-03 | `POST /api/v1/notifications` sin `metadata` | `400` | [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md) | Planeado |

Los escenarios de humo no publican en Kafka: todos cortan en la validación del payload.

### Casos que no se automatizan por ahora

| Caso | Motivo |
|---|---|
| C-09, C-10, N-05 | Requieren modificar la configuración de segmentos en DynamoDB durante la prueba |
| C-11, C-12, C-18 | Requieren romper el secreto, el broker o rotar credenciales; se prueban a mano |
| C-13, C-14, N-06 | El comportamiento actual es un defecto ([observaciones 2 y 3](observaciones.md#2-body-vacío-responde-202-sin-publicar)); se automatizan con el bug correspondiente |
| C-15, C-16, C-17 | Bajo valor en aceptación; cubiertos por las pruebas unitarias del `Handler` o manualmente |
| H-01 a H-03 | El estado del health depende de envíos previos; ver [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md) |

## Pruebas unitarias de la rama

Desde `queuer_ms/`:

```bash
./gradlew test
```

Clases de prueba agregadas: `HandlerTest`, `RouterRestTest`, `PublishCampaignUseCaseTest`, `PublishNotificationUseCaseTest`, `SegmentRoutingAdapterTest`, `KafkaPublisherGatewayAdapterTest`, `KafkaProducerConfigTest`, `ResilientKafkaProducerTest`, `KafkaHealthIndicatorTest`, `KafkaSecretProviderTest`, `ReactiveCommonsConfigTest`.
