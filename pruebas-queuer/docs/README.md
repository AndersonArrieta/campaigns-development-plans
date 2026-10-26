# queuer_ms — Kafka REST Proxy (campañas y notificaciones)

Documentación de los endpoints agregados en la rama `feature/7931497-queuer-ms-kafka-rest-proxy` (último commit revisado: `cecc318af`).

La rama convierte a `queuer_ms` en un **proxy HTTP → Kafka**: recibe eventos de campañas y de notificaciones por REST, resuelve el segmento del `applicationIdentifier` contra la configuración de segmentos y destinos en DynamoDB y publica el evento en el tópico Kafka de ese segmento, con las credenciales del secreto de AWS Secrets Manager configurado para él.

## Endpoints nuevos

| Método | Ruta | Descripción | Tópico destino (clave en `segments_destinies.<segmento>.kafka`) | Doc |
|---|---|---|---|---|
| `POST` | `/campaigns` | Publica un evento de campaña masiva | `campaigns` | [POST-api-v1-campaigns.md](endpoints/POST-api-v1-campaigns.md) |
| `POST` | `/notifications` | Publica un evento de notificación en línea | `notifications` | [POST-api-v1-notifications.md](endpoints/POST-api-v1-notifications.md) |

Hasta [T-021](../backlog/tasks/T-021-quitar-prefijo-api-v1.md) las rutas eran `/api/v1/campaigns` y `/api/v1/notifications`; T-021 quitó el prefijo `/api/v1` y las rutas viejas responden `404`. Los archivos de `endpoints/` conservan el nombre `POST-api-v1-*.md` para no romper enlaces.

El endpoint existente `POST /queuer` (operación `VariableSetter`) no cambia de comportamiento; solo se reescribió el `switch` como un `if`.

## Índice

- [Endpoint `POST /campaigns`](endpoints/POST-api-v1-campaigns.md)
- [Endpoint `POST /notifications`](endpoints/POST-api-v1-notifications.md)
- [Publicación en Kafka: enrutamiento, secretos, resiliencia y health](publicacion-kafka.md)
- [Guía de pruebas y casos de prueba](pruebas.md)
- [Observaciones de la revisión](observaciones.md)
- [Backlog de pruebas](../backlog/README.md)

## Backlog de pruebas

El trabajo para automatizar estos casos en las pruebas de despliegue de `queuer_ms` (`deployment/acceptanceTest` y `deployment/smokeTest`, Karate) está en [`../backlog/`](../backlog/README.md), vault de Obsidian en modo agente. La cola de ejecución está en [`dashboards/ready-queue.md`](../backlog/dashboards/ready-queue.md).

| Tarjeta | Qué cubre |
|---|---|
| [T-001](../backlog/tasks/T-001-parametrizar-karate-config.md) | `baseUrl`, `kafkaReadTimeout` y `kafkaAppId` en los `karate-config.js` |
| [T-002](../backlog/tasks/T-002-verificar-exposicion-rutas.md) | Exposición de `/api/v1/*` por VirtualService y Cognito en `dev` |
| [T-003](../backlog/tasks/T-003-datos-prueba-kafka-dev.md) | Datos de prueba Kafka en `dev` (appId, segmento, secreto, tópicos) |
| [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Aceptación de `POST /api/v1/campaigns` |
| [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Aceptación de `POST /api/v1/notifications` |
| [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md) | Humo de las dos rutas sin publicar en Kafka |
| [T-007](../backlog/tasks/T-007-evidencias-y-trazabilidad.md) | Ejecución en `dev`, evidencias y trazabilidad |
| [T-008](../backlog/tasks/T-008-exposicion-rutas-qa.md) | Exposición de `/campaigns` y `/notifications` en QA para las pruebas modulares |
| [T-009](../backlog/tasks/T-009-datos-carga-kafka-qa.md) | Datos de carga y destino Kafka en QA |
| [T-010](../backlog/tasks/T-010-parametrizar-sc-queuer.md) | Variables nuevas en `SC_queuer.jmx`, retrocompatibles con `GH_queuer` |
| [T-011](../backlog/tasks/T-011-carga-campaigns-jmeter.md) | Grupo de carga JMeter de `POST /campaigns` |
| [T-012](../backlog/tasks/T-012-carga-notifications-jmeter.md) | Grupo de carga JMeter de `POST /notifications` |
| [T-013](../backlog/tasks/T-013-validacion-kafka-modular.md) | Validación en Kafka al cierre de la carga |
| [T-014](../backlog/tasks/T-014-ejecucion-modular-qa.md) | Ejecución en QA, línea base y evidencias |
| [T-015](../backlog/tasks/T-015-prerrequisitos-e2e-qa.md) | Prerrequisitos E2E en QA: del queuer al fakechannel |
| [T-016](../backlog/tasks/T-016-interaccion-envio-queuer.md) | Interacción Screenplay para enviar por el queuer y validar el `202` |
| [T-017](../backlog/tasks/T-017-e2e-notificaciones-queuer.md) | E2E de notificaciones por el queuer (WhatsApp y Teams) |
| [T-018](../backlog/tasks/T-018-e2e-campanas-queuer.md) | E2E de campañas por el queuer (WhatsApp y Teams) |
| [T-019](../backlog/tasks/T-019-pipeline-queuer-ms-test.md) | Suite `Queuer` en el pipeline de `queuer_ms_test` |
| [T-020](../backlog/tasks/T-020-ejecucion-e2e-qa.md) | Ejecución E2E en QA y evidencias |

El detalle de qué escenario cubre cada caso está en [pruebas.md — Automatización en Karate](pruebas.md#automatización-en-karate), [pruebas.md — Pruebas modulares](pruebas.md#pruebas-modulares-jmeter) y [pruebas.md — Pruebas E2E](pruebas.md#pruebas-e2e-serenity). Las pruebas modulares (T-008 a T-014) viven en el repo `NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms`, y las E2E (T-015 a T-020) en `NU0284001_Artemis_Chatbots_Platform_MR_Test` (`Platform_test` + `queuer_ms_test`).

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

    C->>H: POST /campaigns | /notifications
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
| Entry point | `reactive-web` | `RouterRest` | Registra las rutas `/campaigns` y `/notifications` |
| Entry point | `reactive-web` | `Handler#handleCampaignRequest` / `#handleNotificationRequest` | Valida el payload, mapea a dominio y traduce errores a HTTP |
| Entry point | `reactive-web` | `dto/kafka/*` | DTOs de entrada con Bean Validation |
| Dominio | `model` | `CampaignEvent`, `NotificationEvent`, `ResolvedKafkaTarget` | Modelos de dominio |
| Dominio | `model` | `SegmentRoutingGateway`, `KafkaPublisherGateway` | Puertos |
| Dominio | `usecase` | `PublishCampaignUseCase`, `PublishNotificationUseCase` | Orquestan resolución de destino y publicación |
| Driven adapter | `dynamo-db` | `SegmentRoutingAdapter` | Resuelve segmento → tópico + secreto |
| Driven adapter | `kafka-producer` (nuevo) | `KafkaPublisherGatewayAdapter`, `KafkaProducerConfig`, `ResilientKafkaProducer`, `KafkaHealthIndicator` | Publicación resiliente y health |
| Helper | `secret-manager` (nuevo) | `KafkaSecretProvider`, `KafkaProps` | Lectura y cache de secretos Kafka |
| App | `app-service` | `ReactiveCommonsConfig` | Registra el bean `ResponseValidator` |
