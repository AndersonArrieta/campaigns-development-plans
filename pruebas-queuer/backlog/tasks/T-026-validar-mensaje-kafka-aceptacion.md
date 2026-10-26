---
id: T-026
aliases: [T-026]
title: "Validar en Kafka el mensaje publicado en los escenarios 202 de aceptación"
status: blocked
priority: P1
epic: E-aceptacion
estimate: L
depends_on: [T-022, T-025]
affects: [T-004, T-005]
type: task
created: 2026-10-26
---

# T-026 — Validar en Kafka el mensaje publicado en los escenarios `202` de aceptación

## Objetivo
Hoy los escenarios `202` de aceptación (AC-C01, AC-C02, AC-N01 y AC-N02) solo comprueban la respuesta HTTP. Esta tarjeta agrega la comprobación de que el mensaje **llegó al tópico** con la key y el contenido esperados, con el mismo enfoque que `transcribe_ms/deployment/acceptanceTest`:
- `SecretManager.java` lee del secreto de Kafka (`username`, `password`, `bootstrapserver`) con credenciales AWS que llegan como propiedades del sistema, y las guarda en `Memory`.
- `KafkaManager.java` crea un consumidor SASL_SSL `SCRAM-SHA-512` con truststore, hace `assign()` sobre todas las particiones, se posiciona con `offsetsForTimes()` unos minutos hacia atrás y hace `poll` hasta encontrar el mensaje o agotar el timeout.
- Features helper (`kafka-manager.feature`, `secret-manager.feature`) exponen esas clases a Karate con `Java.type`.

Diferencias respecto a `transcribe_ms`:
- El queuer publica y la suite solo **consume**: no hace falta productor.
- El mensaje se busca por **key** (`metadata.Id`, único por escenario con `qacc-<uuid>`) y no por `userIdentifier`, porque todos los escenarios usan `573000000000`.
- El consumidor no se une al consumer group de `platform_campaigns_ms` y no hace commit de offsets (`enable.auto.commit=false`, `assign()` sin `subscribe()`).

## Documentación relacionada
- [Mensaje publicado de campañas](../../docs/endpoints/POST-api-v1-campaigns.md#mensaje-publicado-en-kafka)
- [Mensaje publicado de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md#mensaje-publicado-en-kafka)
- [Observación 1: casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)
- Datos de tópicos, secreto y credenciales: [[T-025-datos-validacion-kafka-aceptacion|T-025]]
- Referencia: `transcribe_ms/deployment/acceptanceTest` (`components/kafka/KafkaManager.java`, `components/aws/SecretManager.java`, `models/Memory.java`, `helpers/*.feature`, `karate-config.js`, `certificates/cacerts`)

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/build.gradle` (dependencias `org.apache.kafka:kafka-clients`, `software.amazon.awssdk:secretsmanager` con su BOM)
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/kafka/KafkaManager.java` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/aws/SecretManager.java` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/models/Memory.java` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/helpers/kafka-manager.feature` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/helpers/secret-manager.feature` (nuevo)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/certificates/cacerts` (nuevo, según T-025)
- `queuer_ms/deployment/acceptanceTest/src/test/resources/karate-config.js`
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/campaigns_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/notifications_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/README.md`
- `pruebas-queuer/docs/pruebas.md`

## Tareas
- [x] `build.gradle`: agregar `kafka-clients` y `secretsmanager` (BOM `software.amazon.awssdk:bom`), con versiones compatibles con Karate `1.0.1` y el JDK del pipeline. Revisar que no reintroducen CVE ya corregidos en el archivo.
- [x] `Memory.java` y `SecretManager.java`: adaptar los de `transcribe_ms` a un solo secreto (`kafkaSecretName`). Región `us-east-1`. Mensajes y comentarios en español sin tildes.
- [x] `KafkaManager.java`: solo consumo. Método `consumeMessageByKey(topic, key, timeoutSeconds)` que devuelve el `value` (o `null`). Usar `assign()`, `offsetsForTimes(ahora - lookback)`, `enable.auto.commit=false`, `group.id` efímero (`queuer-acceptance-<uuid>`) solo si el cliente lo exige. No imprimir credenciales: el `System.out.println(props)` de `transcribe_ms` incluye `sasl.jaas.config` con la contraseña y **no se copia**.
- [x] Helpers: `secret-manager.feature@setSecrets` y `kafka-manager.feature@consume_message_by_key`.
- [x] `karate-config.js`: nuevas propiedades `kafkaSecretName`, `kafkaBatchTopic` (campañas) y `kafkaOnlineTopic` (notificaciones), con los mismos nombres que las variables del release de `platform_campaigns_ms` (ver T-025), `kafkaMessageWaitSeconds` (por defecto `60`) y `kafkaValidate` (por defecto `true`). Si `kafkaValidate` es `true` y falta alguna obligatoria, fallar con un mensaje claro como en `transcribe_ms`. `truststorePassword` y `aws.*` se leen como propiedades del sistema desde Java.
- [x] Features de aceptación: en AC-C01, AC-C02, AC-N01 y AC-N02, después del `202`, leer los secretos con `callonce` y consumir por key = `metadata.Id`. Validar:
  - que el mensaje existe (si no, `karate.fail` con la key y el tópico);
  - `data` del mensaje contiene el `data` enviado (`applicationIdentifier`, `userIdentifier`, `sourceChannel`, identificadores y `message` en notificaciones; en AC-C02 los opcionales quitados llegan como `null` o ausentes);
  - el id de `metadata` es el enviado, aceptando `Id` o `id` (`(msg.metadata.Id || msg.metadata.id) == metadataId`) para que el escenario no dependa de la corrección de la observación 1. Registrar con `karate.log` el casing observado como evidencia.
- [x] Los escenarios `400`, `403` y `422` no cambian: no publican y no consultan Kafka.
- [x] README de `acceptanceTest`: documentar las propiedades nuevas, cuáles son secretas y el ejemplo de ejecución.
- [x] `docs/pruebas.md`: indicar que AC-C01, AC-C02, AC-N01 y AC-N02 validan el mensaje en Kafka y las propiedades nuevas del release.
- [x] Avisar al usuario de las variables nuevas que hay que crear en el release de aceptación (no se crean desde aquí).

## Criterios de aceptación
- [ ] En `dev`, AC-C01, AC-C02, AC-N01 y AC-N02 encuentran su mensaje en el tópico correcto por `metadata.Id` y validan su contenido.
- [ ] Si se cambia un tópico por otro que no recibe el mensaje, el escenario falla por timeout con un mensaje que indica key y tópico.
- [ ] Suite completa en verde en `dev`: 36/36 (desde B-002 `get-token` y el helper ya no corren como features propios).
- [ ] Ningún log ni reporte muestra contraseñas, `sasl.jaas.config`, credenciales AWS ni la contraseña del truststore.
- [ ] El consumidor no aparece como miembro del consumer group de `platform_campaigns_ms`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
# Local: solo compilacion
./gradlew clean compileTestJava

# dev (con la rama desplegada): esta es la validacion que cierra la tarjeta
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  -DkafkaSecretName="$KAFKA_SECRET_NAME" -DkafkaBatchTopic="$KAFKA_BATCH_TOPIC" -DkafkaOnlineTopic="$KAFKA_ONLINE_TOPIC" \
  -DtruststorePassword="$TRUSTSTORE_PASSWORD" \
  -Daws.accessKeyId="$AWS_ACCESS_KEY_ID" -Daws.secretKey="$AWS_SECRET_ACCESS_KEY" -Daws.sessionToken="$AWS_SESSION_TOKEN" \
  -i | grep -E "scenarios|passed|failed"
# Revisar que no se filtran secretos en el log ni en el reporte
grep -rEi "password=|sasl.jaas|secretKey|sessionToken" target/karate.log build/ 2>/dev/null | head
```

## Notas
- **Solo se valida en `dev`.** En local solo se comprueba que compila. La tarjeta se cierra con la suite en verde en `dev`. Si faltan datos de T-025 o las variables del release, queda en `blocked` con esa nota.
- Depende de T-022 porque los features ya tienen que usar `/campaigns` y `/notifications`.
- T-004 y T-005 son `done` y no se editan. Esta tarjeta las enlaza con `affects`.
- Cada corrida sigue publicando 2 campañas y 2 notificaciones en `dev`. `platform_campaigns_ms` las procesa como hoy.
- Alternativa para el truststore (ver notas de [[T-025-datos-validacion-kafka-aceptacion|T-025]]): tomar el CA de la clave `certificate.cer` del secreto con `ssl.truststore.type=PEM`, como `Platform_test/.../utils/aws/service/Kafka.java`. Así no hace falta `cacerts` ni `truststorePassword`. Confirmar en T-025 que el secreto de `dev` trae esa clave.
- 2026-10-26 — Ejecutada con T-022 en `blocked`, igual que T-022 y T-023: misma rama (`feature/7978702_queuer_acceptance_tests`) y mismo despliegue. Sin commit.
- Archivos nuevos: `components/kafka/KafkaManager.java`, `components/aws/SecretManager.java`, `models/Memory.java`, `helpers/kafka-manager.feature` (`@ignore`) y `certificates/cacerts` (copia del de `platform_campaigns_ms`, md5 `d8b6a2194ec18c8a8f080df84928f3ab`). Modificados: `build.gradle` (BOM `software.amazon.awssdk:bom:2.36.0`, `secretsmanager`, `kafka-clients:4.1.0`, mismas versiones que `transcribe_ms`; el pipeline usa JDK 21), `karate-config.js`, los dos features de aceptación y el README.
- Decisiones de implementación:
  - Un solo helper (`kafka-manager.feature`) consume y valida; el secreto se lee una vez desde Java y queda en caché en `Memory`, así que no se creó `secret-manager.feature`.
  - Truststore: primero `certificate.cer` del secreto en PEM (como `Platform_test`); si no viene, `cacerts` con `-DtruststorePassword`.
  - Credenciales AWS: `-Daws.accessKeyId`, `-Daws.secretKey` o `-Daws.secretAccessKey`, `-Daws.sessionToken`; si no llegan, la cadena por defecto de AWS.
  - Consumidor con `assign()`, `offsetsForTimes(ahora - 5 min)`, `group.id` `queuer-acceptance-<uuid>`, `enable.auto.commit=false`. No imprime `sasl.jaas.config` ni credenciales.
  - Validación: mensaje con key = `metadata.Id`, id de `metadata` igual (acepta `Id` o `id`, se registra en el log qué claves trae) y `data` `contains deep` el `data` enviado.
  - `kafkaValidate=false` desactiva la validación en Kafka. Con `true` (por defecto), `karate-config.js` falla si faltan `kafkaSecretName`, `kafkaBatchTopic` u `kafkaOnlineTopic`: **el release de aceptación necesita esas variables antes de desplegar esta rama**, o pasar `-DkafkaValidate=false` mientras tanto.
- Verificación local: `compileTestJava` OK (con VPN). En un feature temporal del scratchpad se comprobó con Karate 1.0.1 que `json x = <string>`, `karate.keysOf`, `contains deep`, `if (...) karate.call(...)` y `Java.type` funcionan, que un `data` distinto hace fallar al escenario que llama y que un tópico vacío falla con `El topico es obligatorio`.
- Variables nuevas para el release de aceptación de `queuer_ms`: `kafkaSecretName`, `kafkaBatchTopic`, `kafkaOnlineTopic` (enlazar las de `platform_campaigns_ms`) y las credenciales `aws.*` (secretas). `truststorePassword` solo si el secreto no trae `certificate.cer`.
- **blocked:** falta crear las variables del release, desplegar en `dev` y correr la suite (37/37), revisar que no se filtran secretos y que el consumer group de `platform_campaigns_ms` no cambia.
- 2026-10-26 — **Corrección ([[B-003-topico-kafka-queuer-no-coincide|B-003]]):** los valores de `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` no se enlazan con las variables de `platform_campaigns_ms` (son del segmento `client-countries`). Para `others-test` son los del segmento `others`: `thirdpartycampaignexecution.initiatecampaignv1`, `thirdpartycampaignmanagement.executenotificationv1` y `nu0284001-artemis-dev-secret-operative-eda-experiencia-trv`, como variables propias del release. Corrida local con esos valores: 35/36 (el único fallo fue de red); con B-001 y B-002 el total es 36, no 37.

