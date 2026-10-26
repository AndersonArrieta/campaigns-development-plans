---
id: T-027
aliases: [T-027]
title: "Tomar el truststore de Kafka solo del CA del secreto y quitar el cacerts"
status: blocked
priority: P1
epic: E-aceptacion
estimate: S
depends_on: [T-026]
affects: [T-026]
type: task
created: 2026-10-26
---

# T-027 — Tomar el truststore de Kafka solo del CA del secreto y quitar el `cacerts`

## Objetivo
Cambio solicitado sobre lo implementado en [[T-026-validar-mensaje-kafka-aceptacion|T-026]]: el consumidor de Kafka de la suite de aceptación toma el truststore **solo** del CA que trae el secreto de Secrets Manager (clave `certificate.cer`, en PEM). Se quita la alternativa del archivo `certificates/cacerts` con `-DtruststorePassword`.

Así la suite no versiona un truststore ni necesita la variable secreta `truststorePassword` en el release. Si el secreto no trae `certificate.cer` o no es un certificado legible, la validación falla con un mensaje claro, en vez de caer al truststore del JDK.

## Documentación relacionada
- Notas de [[T-025-datos-validacion-kafka-aceptacion|T-025]] (truststore PEM desde el secreto, como `Platform_test/.../utils/aws/service/Kafka.java`)
- [Propiedades de ejecución](../../docs/pruebas.md#propiedades-de-ejecución)

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/kafka/KafkaManager.java`
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/aws/SecretManager.java`
- `queuer_ms/deployment/acceptanceTest/src/test/resources/certificates/cacerts` (eliminar)
- `queuer_ms/deployment/acceptanceTest/README.md`
- `pruebas-queuer/docs/pruebas.md`

## Tareas
- [x] `SecretManager.java`: `certificate.cer` pasa a ser clave obligatoria del secreto (`required`), igual que `bootstrapserver`, `username` y `password`.
- [x] `KafkaManager.java`: `configureTruststore` usa solo `ssl.truststore.type=PEM` y `ssl.truststore.certificates` con el CA normalizado. Si `normalizeCertificate` devuelve `null`, lanzar `IllegalStateException` con un mensaje que nombre el secreto y la clave `certificate.cer`, sin incluir su contenido. Quitar `TRUSTSTORE_PATH`, la rama de `truststorePassword` y el uso del truststore del JDK.
- [x] Eliminar `src/test/resources/certificates/cacerts` (y la carpeta si queda vacía).
- [x] README de `acceptanceTest`: quitar la fila `truststorePassword`, indicar en `kafkaSecretName` que `certificate.cer` es obligatoria y ajustar el párrafo del truststore.
- [x] `docs/pruebas.md`: quitar `truststorePassword` de las propiedades de la validación en Kafka.
- [x] Confirmar con `grep -rn "truststorePassword\|cacerts" queuer_ms/deployment/acceptanceTest/src queuer_ms/deployment/acceptanceTest/README.md` que no quedan referencias.

## Criterios de aceptación
- [x] `compileTestJava` pasa en local.
- [x] No queda `cacerts` en `acceptanceTest` ni referencias a `truststorePassword`.
- [ ] En `dev`, AC-C01, AC-C02, AC-N01 y AC-N02 encuentran su mensaje en Kafka con el CA del secreto. Suite completa 36/36.
- [ ] Si el secreto no trae `certificate.cer`, el escenario falla con un mensaje que nombra la clave faltante y no muestra secretos.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
grep -rn "truststorePassword\|cacerts" src README.md   # sin resultados
# Local: solo compilacion (gradlew tiene CRLF en WSL; usar el jar del wrapper)
java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain clean compileTestJava

# dev (con la rama desplegada): esta es la validacion que cierra la tarjeta
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  -DkafkaSecretName="$KAFKA_SECRET_NAME" -DkafkaBatchTopic="$KAFKA_BATCH_TOPIC" -DkafkaOnlineTopic="$KAFKA_ONLINE_TOPIC" \
  -Daws.accessKeyId="$AWS_ACCESS_KEY_ID" -Daws.secretKey="$AWS_SECRET_ACCESS_KEY" -Daws.sessionToken="$AWS_SESSION_TOKEN" \
  -i | grep -E "scenarios|passed|failed"
```

## Notas
- **Solo se valida en `dev`.** En local solo se comprueba que compila. Se cierra junto con T-026 en el mismo despliegue. Si la rama aún no está desplegada, queda en `blocked` con esa nota.
- Va en la misma rama que T-026 (`feature/7978702_queuer_acceptance_tests`).
- Al cerrar esta tarjeta, la variable `truststorePassword` deja de ser necesaria en el release de aceptación de `queuer_ms`.
- 2026-10-26 — Ejecutada con T-026 en `blocked`, por el mismo criterio (misma rama y despliegue). Rama `feature/7978702_queuer_acceptance_tests`, sin commit. T-026 ya estaba commiteada (`a1d87b0ef`, incluía `cacerts`).
- Cambios: `certificate.cer` obligatoria en `SecretManager`; `configureTruststore` solo PEM y lanza `IllegalStateException` con el nombre del secreto si el CA no es legible (`Memory.getKafkaSecretName()` nuevo); se quitan `TRUSTSTORE_PATH`, la rama `truststorePassword` y el truststore del JDK; se elimina `certificates/cacerts` (y la carpeta). README y `docs/pruebas.md` sin `truststorePassword`.
- Verificación local: `grep "truststorePassword\|cacerts"` sobre `src` y README sin resultados; `compileTestJava` OK. `git diff --ignore-cr-at-eol` toca solo README, `SecretManager`, `KafkaManager`, `Memory` y el borrado de `cacerts` (el resto de archivos que `git status` marca como modificados es ruido de CRLF).
- **blocked:** falta validar en `dev` junto con T-026 (37/37 con el CA del secreto).
