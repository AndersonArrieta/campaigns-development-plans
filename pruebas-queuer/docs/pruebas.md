# Guía de pruebas

## Prerrequisitos

1. **Configuración de segmentos en DynamoDB** con el `appId` de prueba dentro de algún segmento y su bloque `kafka` completo (`campaigns`, `notifications`, `secret_campaigns`). Ver [publicacion-kafka.md](publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter).
2. **Secreto en Secrets Manager** con el nombre de `secret_campaigns` y las claves `username`, `password`, `bootstrapserver`.
3. **Tópicos creados** en el broker y permisos de escritura para el usuario del secreto.
4. Para ejecución local: perfil `local` (conexión `PLAINTEXT`, LocalStack en `http://localhost:4566`) y `spring.profiles.active` definido, porque `KafkaProducerConfig` lo inyecta sin valor por defecto.

## Datos de prueba en dev

Definidos en [T-003](../backlog/tasks/T-003-datos-prueba-kafka-dev.md) y verificados el 2026-10-23 con curl contra `dev`:

| Dato | Valor | Estado |
|---|---|---|
| `kafkaAppId` (escenarios `202`) | `others-test` | Aprobado. `POST /campaigns` y `/notifications` responden `202` (el segmento tiene tópico y secreto Kafka) |
| `userIdentifier` ficticio | `57300000` + 4 dígitos aleatorios por escenario (`573000000000`–`573000009999`) | Aprobado (rango ficticio, [T-032](../backlog/tasks/T-032-user-identifier-aleatorio-ficticio.md)) |
| `appId` sin segmento (escenarios `422`) | `queuer-acceptance-sin-segmento` | Verificado: `422 No existe segmento configurado para applicationIdentifier: queuer-acceptance-sin-segmento` |
| `metadata.Id` | `qacc-<runId>-<c\|n>` | Recomendado, para identificar en el tópico los mensajes de cada corrida |

- El primer `POST /campaigns` tras un tiempo sin tráfico tardó ~4 s (lectura del secreto y creación del productor); por eso los escenarios Kafka usan `kafkaReadTimeout`.
- No se leyó el item de segmentos en DynamoDB ni el secreto en Secrets Manager (sin sesión de AWS); el segmento concreto de `others-test` y los nombres de tópicos no están confirmados.
- Cada ejecución de la suite de aceptación publica en los tópicos de `dev`.
- Para leer de Kafka el mensaje publicado, la suite usa los tópicos y el secreto del segmento de `kafkaAppId`. `others-test` está en el segmento `others`: `kafkaBatchTopic` = `thirdpartycampaignexecution.initiatecampaignv1`, `kafkaOnlineTopic` = `thirdpartycampaignmanagement.executenotificationv1`, `kafkaSecretName` = `nu0284001-artemis-dev-secret-operative-eda-experiencia-trv` (clúster `strimzi-exp-trv-dev`). **No** son las variables de la aceptación de `platform_campaigns_ms`, que corresponden al segmento `client-countries`. Ver [B-003](../backlog/bugs/B-003-topico-kafka-queuer-no-coincide.md); el segmento de un app se consulta con [`scripts/leer_segmento_kafka.py`](../scripts/README.md).

## Casos de prueba

Base URL local: `http://localhost:8080`.

<a id="post-apiv1campaigns"></a>

### `POST /campaigns`

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

<a id="post-apiv1notifications"></a>

### `POST /notifications`

| # | Caso | Preparación / payload | Esperado |
|---|---|---|---|
| N-01 | Publicación exitosa | Payload válido | `202`, `{"status":"accepted","message":"Notification event accepted for Kafka publication"}`; mensaje en tópico `notifications` |
| N-02 | Falta `data.notification.message` | Omitir `message` | `400`, `El campo 'data.notification.message' es obligatorio` |
| N-03 | Falta `data.notification` | Omitir `notification` | `400`, `El objeto 'data.notification' es obligatorio` |
| N-04 | `appId` sin segmento | `applicationIdentifier: "no_existe"` | `422` |
| N-05 | Segmento sin `kafka.notifications` (pero con `campaigns`) | Quitar `notifications` | `422`, `No existe topico Kafka configurado para el segmento: <seg>`; `/campaigns` sigue funcionando |
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
curl -i -X POST http://localhost:8080/campaigns \
  -H "Content-Type: application/json" -d @campaign.json

# Notificación
curl -i -X POST http://localhost:8080/notifications \
  -H "Content-Type: application/json" -d @notification.json

# Health
curl -s http://localhost:8080/actuator/health

# Verificar el mensaje en el tópico (broker local)
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic <tópico> --from-beginning --property print.key=true
```

## Automatización en Karate

Escenarios que se agregan a las pruebas de despliegue de `queuer_ms`. El trabajo está planificado en el [backlog](../backlog/README.md); [T-007](../backlog/tasks/T-007-evidencias-y-trazabilidad.md) actualiza la columna de estado al ejecutarlos en `dev`.

### Propiedades de ejecución

Agregadas en [T-001](../backlog/tasks/T-001-parametrizar-karate-config.md) a los `karate-config.js` de `acceptanceTest` y `smokeTest`, retrocompatibles con el release actual. Desde [T-024](../backlog/tasks/T-024-eliminar-humo-campaigns-notifications.md) solo existen en `acceptanceTest`: `smokeTest` volvió a su configuración original.

| Propiedad | Por defecto | Uso |
|---|---|---|
| `baseUrl` | `endpoint` sin `/queuer` | URL base para `/campaigns` y `/notifications` |
| `kafkaReadTimeout` | `30000` ms | `readTimeout` de los escenarios Kafka; el global sigue en `2000` ms |
| `kafkaAppId` | — (se define en [T-003](../backlog/tasks/T-003-datos-prueba-kafka-dev.md)) | `applicationIdentifier` de prueba de los escenarios `202` |

Agregadas en [T-026](../backlog/tasks/T-026-validar-mensaje-kafka-aceptacion.md) al `karate-config.js` de `acceptanceTest` para validar en Kafka el mensaje publicado:

| Propiedad | Por defecto | Uso |
|---|---|---|
| `kafkaValidate` | `true` | Activa la validación en Kafka de los escenarios `202`; con `false` solo se valida la respuesta HTTP |
| `kafkaSecretName`, `kafkaBatchTopic`, `kafkaOnlineTopic` | — (obligatorias si `kafkaValidate`) | Secreto y tópicos del segmento de `kafkaAppId` (para `others-test`, los del segmento `others`; variables propias del release del queuer). El secreto debe traer `certificate.cer` (CA del broker): el truststore se arma solo con él |
| `kafkaMessageWaitSeconds` | `60` | Tiempo máximo para encontrar el mensaje |
| `aws.accessKeyId`, `aws.secretKey`/`aws.secretAccessKey`, `aws.sessionToken` | — | Credenciales para leer el secreto (secretas) |

### Aceptación — `queuer_ms/deployment/acceptanceTest`

| Escenario | Caso | Esperado | Tarjeta | Estado |
|---|---|---|---|---|
| AC-C01 | C-01 | `202` + mensaje en `kafkaBatchTopic` (key = `metadata.Id`, `data` igual al enviado) | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md), [T-026](../backlog/tasks/T-026-validar-mensaje-kafka-aceptacion.md) | Implementado |
| AC-C02 | C-02 | `202` + mensaje en `kafkaBatchTopic` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md), [T-026](../backlog/tasks/T-026-validar-mensaje-kafka-aceptacion.md) | Implementado |
| AC-C03 | C-03 | `400` sin `metadata` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C04 | C-04 | `400` `metadata.Id` en blanco | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C05 | — | `400` sin `data.applicationIdentifier` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C06 | C-06 | `400` sin `data.campaign` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C07 | C-07 | `400` sin `notification.dataTime` | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C08 | C-05 | `400` `metadata` en camelCase | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C09 | C-08 | `422` appId sin segmento | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-C10 | — | `403` RBAC | [T-004](../backlog/tasks/T-004-aceptacion-campaigns.md) | Implementado |
| AC-N01 | N-01 | `202` + mensaje en `kafkaOnlineTopic` (key = `metadata.Id`, `data` igual al enviado) | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md), [T-026](../backlog/tasks/T-026-validar-mensaje-kafka-aceptacion.md) | Implementado |
| AC-N02 | — | `202` sin `messageContext` + mensaje en `kafkaOnlineTopic` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md), [T-026](../backlog/tasks/T-026-validar-mensaje-kafka-aceptacion.md) | Implementado |
| AC-N03 | — | `400` sin `metadata` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N04 | — | `400` `metadata.Id` en blanco | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N05 | N-03 | `400` sin `data.notification` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N06 | N-02 | `400` sin `message` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N07 | — | `400` sin `userIdentifier` | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N08 | N-04 | `422` appId sin segmento | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |
| AC-N09 | — | `403` RBAC | [T-005](../backlog/tasks/T-005-aceptacion-notifications.md) | Implementado |

### Humo — `queuer_ms/deployment/smokeTest`

| Escenario | Request | Esperado | Tarjeta | Estado |
|---|---|---|---|---|
| SM-01 | `GET /actuator/health` (existente) | `200` `UP` | — | Existente |
| SM-02 | `POST /campaigns` sin `metadata` | `400` | [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md), [T-024](../backlog/tasks/T-024-eliminar-humo-campaigns-notifications.md) | Eliminado |
| SM-03 | `POST /notifications` sin `metadata` | `400` | [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md), [T-024](../backlog/tasks/T-024-eliminar-humo-campaigns-notifications.md) | Eliminado |

SM-02 y SM-03 se eliminaron en [T-024](../backlog/tasks/T-024-eliminar-humo-campaigns-notifications.md): la suite de humo solo valida el health (SM-01). La exposición de `/campaigns` y `/notifications` queda cubierta por la suite de aceptación. El humo no publica en Kafka.

### Casos que no se automatizan por ahora

| Caso | Motivo |
|---|---|
| C-09, C-10, N-05 | Requieren modificar la configuración de segmentos en DynamoDB durante la prueba |
| C-11, C-12, C-18 | Requieren romper el secreto, el broker o rotar credenciales; se prueban a mano |
| C-13, C-14, N-06 | El comportamiento actual es un defecto ([observaciones 2 y 3](observaciones.md#2-body-vacío-responde-202-sin-publicar)); se automatizan con el bug correspondiente |
| C-15, C-16, C-17 | Bajo valor en aceptación; cubiertos por las pruebas unitarias del `Handler` o manualmente |
| H-01 a H-03 | El estado del health depende de envíos previos; ver [T-006](../backlog/tasks/T-006-humo-endpoints-kafka.md) |

## Pruebas modulares (JMeter)

Pruebas de carga de los endpoints Kafka. Viven en el repo `NU0284001_Artemis_Chatbots_Platform_PE`, en `Back/Modular/queuer_ms/SC_queuer.jmx`, el mismo script que hoy carga `POST /queuer` con el grupo `GH_queuer`. Corren en **QA** (host `informacion-ext-qa.apps.ambientesbc.com`, Cognito `chatbots-artemis-qa`) con el Throughput Shaping Timer, y envían los resultados a Elasticsearch con el Backend Listener (`idPrueba`). El trabajo está en la épica [E-modular](../backlog/epics/E-modular.md).

### Datos de prueba en QA

Se definen en [T-009](../backlog/tasks/T-009-datos-carga-kafka-qa.md) y [T-008](../backlog/tasks/T-008-exposicion-rutas-qa.md):

| Dato | Valor | Estado |
|---|---|---|
| `kafkaAppId` | `performance_test` (el mismo de la prueba modular de `campaigns_ms`). En QA está en el segmento `others`, que publica en `thirdpartycampaignexecution.initiatecampaignv1` (campañas) y `thirdpartycampaignmanagement.executenotificationv1` (notificaciones) | Confirmado en DynamoDB y con `202` manual (2026-10-28) |
| `userIdentifier` | `57` + 10 dígitos aleatorios: en QA el consumidor entrega en `fakechannel`, no en un canal real | Definido |
| `metadata.Id` | `qmod-<runId>-<uuid>`, que es la key Kafka y permite filtrar la corrida | Propuesto |
| `pathCampaigns` / `pathNotifications` | `/artemis/platform/queuer/v1/campaigns` / `/artemis/platform/queuer/v1/notifications` (sin `/api/v1`) | Verificado en [T-008](../backlog/tasks/T-008-exposicion-rutas-qa.md) |
| `path` de `GH_queuer` | `/artemis/platform/queuer/v1/queuer`. El valor por defecto del script (`/artemis/platform/queuer/testing/queuer`) responde `404` en QA | Verificado en [T-008](../backlog/tasks/T-008-exposicion-rutas-qa.md) |

Efecto aguas abajo: cada `202` es un mensaje real en los tópicos `thirdparty*` de QA, que consume `platform_campaigns_ms` y entrega en `fakechannel`. Para validar los mensajes ([T-013](../backlog/tasks/T-013-validacion-kafka-modular.md)) hace falta leer `secret_campaigns`. El rol SSO `FullStackQARole` no tiene `secretsmanager:GetSecretValue` sobre ese secreto.

### Propiedades de `SC_queuer.jmx`

Agregadas en [T-010](../backlog/tasks/T-010-parametrizar-sc-queuer.md). Todas se pasan con `-J<propiedad>=<valor>`; con los valores por defecto los grupos nuevos no generan carga y solo corre `GH_queuer`.

| Propiedad | Por defecto | Uso |
|---|---|---|
| `pathCampaigns` / `pathNotifications` | `/artemis/platform/queuer/v1/campaigns` / `/artemis/platform/queuer/v1/notifications` | Rutas en QA |
| `kafkaAppId` | `performance_test` | `applicationIdentifier` de la carga |
| `campaignsTps` / `notificationsTps` | `0` | TPS por flujo |
| `usersCampaigns` / `usersNotifications` | `0` | Hilos por flujo |
| `rampUpCampaigns` / `rampUpNotifications` | `0` | Rampa por flujo (s) |
| `durationCampaigns` / `durationNotifications` | `0` | Duración por flujo (s) |
| `assertionTimeout` | `2000` | Tiempo máximo de respuesta aceptado (ms) |

`V_runId` (`${__time(yyyyMMddHHmmss)}`) no es propiedad: marca los `metadata.Id` de la corrida (`qmod-<runId>-<uuid>`).

### Escenarios

| Escenario | Transacción | Qué mide | Tarjeta | Estado |
|---|---|---|---|---|
| MOD-C01 | `Tx_modQueuerCampaigns` | Carga por TPS sobre `POST /campaigns`: `202`, `$.status == accepted`, duración ≤ `assertionTimeout` | [T-011](../backlog/tasks/T-011-carga-campaigns-jmeter.md) | Implementado (1 TPS × 60 s en QA: 57/57 `202`, 2 por encima de 2000 ms) |
| MOD-N01 | `Tx_modQueuerNotifications` | Lo mismo sobre `POST /notifications` | [T-012](../backlog/tasks/T-012-carga-notifications-jmeter.md) | Implementado (1 TPS × 60 s en QA: 62/62 `202`, 2 por encima de 2000 ms; la primera corrida en frío tuvo 2 de ~30 s) |
| MOD-K01 | `Tx_validateQueuerTopics` | Al cierre, los mensajes con key `qmod-<runId>-*` en cada tópico coinciden con los `202` | [T-013](../backlog/tasks/T-013-validacion-kafka-modular.md) | Planeado |
| MOD-K02 | `Chk_metadataCasing` | Informativo: casing de `metadata` en el mensaje publicado ([observación 1](observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)) | [T-013](../backlog/tasks/T-013-validacion-kafka-modular.md) | Planeado |

El perfil de carga (TPS, duración) y los umbrales (p95, % de error) se acuerdan en [T-014](../backlog/tasks/T-014-ejecucion-modular-qa.md), donde también se registra la línea base. El grupo `GH_queuer` y las propiedades que hoy usa el release no cambian: los grupos nuevos tienen `0` por defecto y la validación Kafka se activa solo con `-JvalidateKafka=true`.

## Pruebas E2E (Serenity)

Prueban el flujo completo en **QA**:

```
queuer (HTTP) → Kafka → platform_campaigns_ms → adaptador de salida → fakechannel
```

El código vive en el repo `NU0284001_Artemis_Chatbots_Platform_MR_Test`. Los escenarios se escriben en `Platform_test/`, un proyecto Serenity + Cucumber + Screenplay compartido. `queuer_ms_test/azure-pipeline.yaml` elige qué runners y features se empaquetan (hoy solo `IntegratorNode`). El trabajo está en la épica [E-e2e](../backlog/epics/E-e2e.md).

Se reutiliza la suite `Notifications` existente (`PrepareNotificationEvent`, `VerifyChannelDelivery`, `Cognito`, datasets `notifications_e2e_flow` / `campaigns_e2e_flow`). La diferencia es que el evento entra por `POST /campaigns` o `POST /notifications` del queuer en lugar de publicarse directo en Kafka.

### Datos y propiedades

Se confirman en [T-015](../backlog/tasks/T-015-prerrequisitos-e2e-qa.md):

| Propiedad / dato | Valor | Estado |
|---|---|---|
| `-DendpointQueuer` | host + prefijo del queuer en QA (de [T-008](../backlog/tasks/T-008-exposicion-rutas-qa.md)) | Propuesto |
| `-DappId` | `others-test` (valor por defecto de la suite `Notifications`) | Por confirmar que su segmento publica en los tópicos que consume el flujo |
| `-DendpointGetMessageFake`, `-DcognitoEndpoint`, `-DclientId`, `-DclientSecret` | los mismos de la suite `Notifications` | Existentes |
| Nodo y texto de campaña | `N-03-99-10` / `Campaig_e2e_test_delivered_successfully` (dataset `campaigns_e2e_flow`) | Por confirmar con el consumidor |

### Escenarios — `features/queuer.feature`, runner `Queuer`

| Escenario | Flujo | Esperado | Tarjeta | Estado |
|---|---|---|---|---|
| E2E-N01 | Notificación en línea, WhatsApp | `202` del queuer y mensaje entregado en `get-messages` | [T-017](../backlog/tasks/T-017-e2e-notificaciones-queuer.md) | Planeado |
| E2E-N02 | Notificación en línea, Teams | `202` y mensaje entregado | [T-017](../backlog/tasks/T-017-e2e-notificaciones-queuer.md) | Planeado |
| E2E-C01 | Campaña, WhatsApp | `202` y texto del nodo de campaña entregado | [T-018](../backlog/tasks/T-018-e2e-campanas-queuer.md) | Planeado |
| E2E-C02 | Campaña, Teams | `202` y texto del nodo de campaña entregado | [T-018](../backlog/tasks/T-018-e2e-campanas-queuer.md) | Planeado |

Los casos negativos (`400`, `422`) no se repiten en E2E: están cubiertos por la aceptación en Karate ([T-004](../backlog/tasks/T-004-aceptacion-campaigns.md), [T-005](../backlog/tasks/T-005-aceptacion-notifications.md)).

## Pruebas unitarias de la rama

Desde `queuer_ms/`:

```bash
./gradlew test
```

Clases de prueba agregadas: `HandlerTest`, `RouterRestTest`, `PublishCampaignUseCaseTest`, `PublishNotificationUseCaseTest`, `SegmentRoutingAdapterTest`, `KafkaPublisherGatewayAdapterTest`, `KafkaProducerConfigTest`, `ResilientKafkaProducerTest`, `KafkaHealthIndicatorTest`, `KafkaSecretProviderTest`, `ReactiveCommonsConfigTest`.
