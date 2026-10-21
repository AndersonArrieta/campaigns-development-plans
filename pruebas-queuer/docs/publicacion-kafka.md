# Publicación en Kafka

Detalle de lo que ocurre después de que el `Handler` valida el payload: enrutamiento por segmento, obtención de credenciales, envío resiliente y health check.

## 1. Enrutamiento por segmento (`SegmentRoutingAdapter`)

En **cada** request se lee la configuración desde DynamoDB con `ConfigurationRepository#loadAdapterConfiguration()` (no hay cache en este adaptador).

| Propiedad | Variable de entorno |
|---|---|
| Tabla | `CONFIG_REPOSITORY_NAME` |
| `component` (partition key) | `SEGMENTS-DESTINIES-CONFIG-IDENTIFIER` |
| `config_name` (sort key) | `CONFIG-TARGET-NAME` |
| Atributo con el JSON | `data` |

Estructura relevante del JSON almacenado:

```json
{
  "segments": {
    "clients": ["performance_test", "otro_app"],
    "employees": [],
    "client-countries": [],
    "employee-countries": [],
    "others": [],
    "prototype": []
  },
  "segments_destinies": {
    "clients": {
      "rabbitmq": { "...": "..." },
      "kafka": {
        "campaigns": "<tópico de campañas>",
        "notifications": "<tópico de notificaciones>",
        "secret_campaigns": "<nombre del secreto en Secrets Manager>"
      }
    }
  }
}
```

Algoritmo:

1. Recorre `segments` y toma el **primer** segmento cuya lista contiene el `applicationIdentifier` (comparación exacta, sensible a mayúsculas).
2. Toma `segments_destinies.<segmento>.kafka`.
3. Tópico: `kafka.campaigns` (campañas) o `kafka.notifications` (notificaciones).
4. Secreto: `kafka.secret_campaigns` (para **ambos** endpoints).
5. Si falta cualquiera de los anteriores → `IllegalStateException` → HTTP `422`.

Solo se reconocen los segmentos que modela `QueuerConfiguration`: `clients`, `employees`, `client-countries`, `employee-countries`, `others`, `prototype`. Un `appId` registrado únicamente en otro segmento (por ejemplo `pilots`) no se resuelve.

## 2. Credenciales (`KafkaSecretProvider`)

- Lee el secreto de AWS Secrets Manager con el nombre de `secret_campaigns`.
- Cache en memoria por nombre de secreto con TTL de **10 minutos**.
- Formato esperado del secreto:

```json
{
  "username": "<usuario SCRAM>",
  "password": "<password>",
  "bootstrapserver": "broker1:9096,broker2:9096",
  "certificate.cer": "<opcional, no se usa hoy>"
}
```

- Región: `aws.region` (por defecto `us-east-1`). Endpoint: `aws.endpoint` / `aws.endPoint` (LocalStack en local).

## 3. Productor (`KafkaProducerConfig`)

| Propiedad | Valor |
|---|---|
| `bootstrap.servers` | `bootstrapserver` del secreto |
| `client.id` | hostname del pod |
| `key/value.serializer` | `StringSerializer` |
| `acks` | `all` |
| `enable.idempotence` | `true` |
| `security.protocol` | `PLAINTEXT` si `spring.profiles.active` contiene `local`; si no `SASL_SSL` |
| `sasl.mechanism` | `SCRAM-SHA-512` (no local) |

Se mantiene **un productor por secreto** (`ConcurrentHashMap<secretName, ResilientKafkaProducer>`), así que segmentos que comparten secreto comparten conexión.

## 4. Resiliencia

### Reintentos del envío (`ResilientKafkaProducer`)

| Parámetro | Valor |
|---|---|
| Reintentos máximos | 5 |
| Backoff | exponencial, mínimo 2 s, máximo 30 s, jitter 30 % |
| Antes de cada reintento | se cierra y recrea el `KafkaSender` |
| Reintentables | `RetriableException`, `SaslAuthenticationException`, `NetworkException`, cualquier `KafkaException` |
| No reintentables | `SerializationException`, `RecordTooLargeException` |
| Al agotarse | `RuntimeException("[segment-<secreto>] Kafka send failed after 5 attempts")` → HTTP `500` |

Como la respuesta HTTP espera el ack de Kafka, en el peor caso la petición puede tardar **más de un minuto** (≈ 2 + 4 + 8 + 16 + 30 s de backoff, más los timeouts propios del cliente Kafka en cada intento).

### Reintento por autenticación (`KafkaPublisherGatewayAdapter`)

Si el error final (o alguna de sus causas) es `SaslAuthenticationException` / `AuthenticationException`:

1. Marca el health como `UNKNOWN`.
2. Invalida el secreto en cache y descarta el productor de ese secreto.
3. Reintenta **una sola vez** con credenciales recién leídas (cubre la rotación de secretos).

## 5. Health check (`KafkaHealthIndicator`)

Expuesto en `/actuator/health` (componente `kafka`; nombre configurable con `kafka.health.component-name`, por defecto `kafka-producer`).

| Estado | Cuándo |
|---|---|
| `UNKNOWN` | Al arrancar (`Esperando primer envio a Kafka`) o durante reintento por autenticación |
| `UP` | Tras una publicación exitosa |
| `DOWN` | Tras una publicación fallida; incluye `reason` con el mensaje del error |

El estado es **global**: un fallo en un segmento marca `DOWN` aunque otros segmentos publiquen bien, hasta el siguiente envío exitoso. Cualquier error del flujo de publicación lo marca `DOWN`, incluidos los de configuración del secreto.

## 6. Dependencias y módulos nuevos

- `infrastructure/driven-adapters/kafka-producer` (`reactor-kafka`, actuator).
- `infrastructure/helpers/secret-manager` (conector async de Secrets Manager de Bancolombia).
- Registrados en `settings.gradle` y como dependencias de `app-service`.
