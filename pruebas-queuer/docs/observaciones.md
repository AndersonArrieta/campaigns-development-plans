# Observaciones de la revisión

Hallazgos al revisar la rama `feature/7931497-queuer-ms-kafka-rest-proxy` (commit `cecc318af`). Conviene validarlos en las pruebas antes de liberar.

## 1. El mensaje publicado cambia el casing de `metadata`

**Impacto: alto (contrato con el consumidor).**

El request exige `metadata.Id`, `metadata.Source`, … en PascalCase (`@JsonProperty("Id")` en los DTOs), pero lo que se publica es el modelo de dominio `CampaignEvent` / `NotificationEvent`, que no tiene `@JsonProperty`. El `ObjectMapper` lo serializa como `id`, `source`, `specVersion`, etc.

El consumidor `platform_campaigns_ms` deserializa `metadata` con `CampaignEventMetadataDto`, que espera PascalCase. Resultado esperado: los valores de `metadata` llegan en `null` al consumidor o, si su `ObjectMapper` tiene `FAIL_ON_UNKNOWN_PROPERTIES` activo, el mensaje falla al deserializar. Según la documentación del consumidor, hoy ningún caso de uso lee `metadata`, así que el impacto inmediato sería bajo en el primer escenario.

**Sugerencia:** agregar `@JsonProperty("Id")`, etc., a `CampaignEvent.Metadata` y `NotificationEvent.Metadata`, o publicar un DTO de salida con el contrato del tópico.

## 2. Body vacío responde `202` sin publicar

`request.bodyToMono(...)` devuelve `Mono.empty()` cuando no hay body; la cadena `flatMap/map` no se ejecuta y `.then(ServerResponse.accepted()...)` responde `202 accepted` sin enviar nada a Kafka. El cliente cree que el evento quedó publicado.

**Sugerencia:** `.switchIfEmpty(Mono.error(new IllegalArgumentException("Payload vacio o mal formado")))` después de `bodyToMono`. La validación `request == null` que existe hoy nunca se cumple.

## 3. JSON mal formado responde `500` en vez de `400`

Un JSON inválido, un tipo incorrecto (p. ej. `messageContext` como string) o un `Content-Type` no soportado producen `ServerWebInputException` / `UnsupportedMediaTypeStatusException`, que caen en el `onErrorResume(Exception.class)` y se responden como `500 Error tecnico ...`. Son errores del cliente.

## 4. Errores de secreto se responden como `422` y exponen el nombre del secreto

`KafkaSecretProvider` y `KafkaProducerConfig` lanzan `IllegalStateException` cuando no pueden leer el secreto o este está incompleto. El `Handler` mapea toda `IllegalStateException` a `422` con el mensaje original, por lo que un fallo de infraestructura (Secrets Manager caído, permisos IAM) se presenta como error de negocio y el body incluye el nombre del secreto (`No fue posible obtener el secreto de Kafka: <nombre>`).

## 5. Latencia del endpoint atada a los reintentos de Kafka

El `202` se emite tras el ack de Kafka. Con 5 reintentos y backoff de hasta 30 s, una indisponibilidad del broker deja la petición abierta más de un minuto. Revisar el timeout del cliente y del API Gateway / balanceador; si cortan antes, el cliente ve un timeout aunque el evento pueda terminar publicándose (posible duplicado si reintenta).

Además, `isRetryable` reintenta cualquier `KafkaException`, incluidos errores no transitorios como `TopicAuthorizationException` o tópico inexistente.

## 6. `KafkaSecretProvider#loadSecret` usa `.block()`

La lectura del secreto se hace con `block()` dentro de `computeIfAbsent`, en el hilo del flujo reactivo. Con cache de 10 min ocurre poco, pero en el primer request por secreto (o tras invalidación) bloquea el hilo que esté ejecutando el flujo. Si ese hilo es uno no bloqueable de Reactor/Netty, `block()` lanza `IllegalStateException`, que el `Handler` respondería como `422`. Conviene probarlo con el pod recién levantado (caso C-01 como primer request).

## 7. Segmentos no modelados

`SegmentRoutingAdapter` convierte `QueuerConfiguration` a `Map`, así que solo ve los segmentos declarados en el modelo (`clients`, `employees`, `clientCountries`, `employeeCountries`, `others`, `prototype`). Otros segmentos presentes en DynamoDB (p. ej. `pilots`, que aparece en la configuración documentada de `platform_campaigns_ms`) se descartan y sus `appId` reciben `422`.

## 8. Health global y sensible a errores de negocio

`KafkaHealthIndicator` tiene un solo estado para todos los segmentos y lo pasa a `DOWN` ante cualquier error del flujo de publicación. Un segmento mal configurado deja `/actuator/health` en `DOWN` (HTTP 503) hasta que otro envío tenga éxito. Si el health agregado se usa en algún monitor o probe, puede generar falsas alarmas.

## 9. Configuración leída de DynamoDB en cada request

`SegmentRoutingAdapter` llama a `loadAdapterConfiguration()` por cada petición, sin cache. Bajo carga, cada evento implica un `GetItem` a DynamoDB.

## 10. Menores

- Mensajes de error con y sin tilde mezclados (`Payload vacío` en campañas, `Payload vacio` en notificaciones).
- `ERROR_ESTRUCTURA_DATOS` cambió de `public` a `private` y perdió la tilde: `POST /queuer` (VariableSetter) ahora responde `400 Estructura de datos invalida.` en vez de `inválida.`. Verificar que ningún cliente compare ese texto.
- El hostname de respaldo en `KafkaProducerConfig` es `AdapterGateway-HostName-Unknown` (copiado de otro componente).
