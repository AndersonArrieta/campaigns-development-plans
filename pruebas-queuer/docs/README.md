# queuer_ms — Kafka REST Proxy (campañas y notificaciones)

Documentación de los endpoints agregados en la rama `feature/7931497-queuer-ms-kafka-rest-proxy` (último commit revisado: `cecc318af`).

La rama convierte a `queuer_ms` en un **proxy HTTP → Kafka**: recibe eventos de campañas y de notificaciones por REST, resuelve el segmento del `applicationIdentifier` contra la configuración de segmentos y destinos en DynamoDB y publica el evento en el tópico Kafka de ese segmento, con las credenciales del secreto de AWS Secrets Manager configurado para él.

## Endpoints nuevos

| Método | Ruta | Descripción | Tópico destino (clave en `segments_destinies.<segmento>.kafka`) | Doc |
|---|---|---|---|---|
| `POST` | `/api/v1/campaigns` | Publica un evento de campaña masiva | `campaigns` | [POST-api-v1-campaigns.md](endpoints/POST-api-v1-campaigns.md) |
| `POST` | `/api/v1/notifications` | Publica un evento de notificación en línea | `notifications` | [POST-api-v1-notifications.md](endpoints/POST-api-v1-notifications.md) |

El endpoint existente `POST /queuer` (operación `VariableSetter`) no cambia de comportamiento; solo se reescribió el `switch` como un `if`.

## Índice

- [Endpoint `POST /api/v1/campaigns`](endpoints/POST-api-v1-campaigns.md)
- [Endpoint `POST /api/v1/notifications`](endpoints/POST-api-v1-notifications.md)
- [Publicación en Kafka: enrutamiento, secretos, resiliencia y health](publicacion-kafka.md)
- [Guía de pruebas y casos de prueba](pruebas.md)
- [Observaciones de la revisión](observaciones.md)

## Flujo general

```mermaid
sequenceDiagram
    autonumber
    participant C as Cliente HTTP
    participant H as Handler (reactive-web)
    participant UC as PublishCampaignUseCase /<br/>PublishNotificationUseCase
    participant SR as SegmentRoutingAdapter
    participant DY as DynamoDB (config segmentos)
    participant KP as KafkaPublisherGatewayAdapter
    participant SM as Secrets Manager
    participant K as Kafka

    C->>H: POST /api/v1/campaigns | /api/v1/notifications
    H->>H: Deserializa DTO + Bean Validation
    alt Payload inválido
        H-->>C: 400 {"error": "..."}
    end
    H->>UC: execute(evento de dominio)
    UC->>UC: Valida data.applicationIdentifier y metadata.Id
    UC->>SR: resolveCampaignTarget / resolveNotificationTarget(appId)
    SR->>DY: loadAdapterConfiguration()
    DY-->>SR: segments + segments_destinies
    SR-->>UC: ResolvedKafkaTarget(segmento, tópico, secreto)
    alt Sin segmento / tópico / secreto
        UC-->>H: IllegalStateException
        H-->>C: 422 {"error": "..."}
    end
    UC->>KP: publish(tópico, secreto, key = metadata.Id, evento)
    KP->>SM: getBySecretName(secreto) (cache 10 min)
    KP->>K: send (acks=all, idempotente, hasta 5 reintentos)
    K-->>KP: ack
    KP-->>H: Mono<Void>
    H-->>C: 202 {"status": "accepted", ...}
```

> El `202 Accepted` se devuelve **después** de que Kafka confirma la escritura (`acks=all`), no antes. La respuesta es síncrona respecto a la publicación.

## Componentes agregados

| Capa | Módulo | Clase | Rol |
|---|---|---|---|
| Entry point | `reactive-web` | `RouterRest` | Registra las rutas `/api/v1/campaigns` y `/api/v1/notifications` |
| Entry point | `reactive-web` | `Handler#handleCampaignRequest` / `#handleNotificationRequest` | Valida el payload, mapea a dominio y traduce errores a HTTP |
| Entry point | `reactive-web` | `dto/kafka/*` | DTOs de entrada con Bean Validation |
| Dominio | `model` | `CampaignEvent`, `NotificationEvent`, `ResolvedKafkaTarget` | Modelos de dominio |
| Dominio | `model` | `SegmentRoutingGateway`, `KafkaPublisherGateway` | Puertos |
| Dominio | `usecase` | `PublishCampaignUseCase`, `PublishNotificationUseCase` | Orquestan resolución de destino y publicación |
| Driven adapter | `dynamo-db` | `SegmentRoutingAdapter` | Resuelve segmento → tópico + secreto |
| Driven adapter | `kafka-producer` (nuevo) | `KafkaPublisherGatewayAdapter`, `KafkaProducerConfig`, `ResilientKafkaProducer`, `KafkaHealthIndicator` | Publicación resiliente y health |
| Helper | `secret-manager` (nuevo) | `KafkaSecretProvider`, `KafkaProps` | Lectura y cache de secretos Kafka |
| App | `app-service` | `ReactiveCommonsConfig` | Registra el bean `ResponseValidator` |
