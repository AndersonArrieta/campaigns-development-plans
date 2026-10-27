---
id: T-031
aliases: [T-031]
title: "Usar java.util.logging.Logger y escribir en inglés el código de la validación en Kafka de la suite de aceptación"
status: done
priority: P2
epic: E-aceptacion
estimate: S
depends_on: []
affects: [T-026, B-002, B-003]
type: task
created: 2026-10-27
---

# T-031 — Usar `java.util.logging.Logger` en lugar de `System.out` en la validación en Kafka de la suite de aceptación

## Objetivo
Cambio solicitado por el usuario en revisión: las clases Java agregadas para validar en Kafka los escenarios `202` de `/campaigns` y `/notifications` escriben con `System.out.println`, y los errores se reportan solo armando el texto de la excepción (por ejemplo, `e.getClass().getSimpleName() + " - " + e.getMessage()`). Deben usar el logger de Java (`java.util.logging.Logger`), como `Platform_test/.../utils/aws/service/Kafka.java`.

## Documentación relacionada
- [[T-026-validar-mensaje-kafka-aceptacion|T-026]], [[B-002-helper-kafka-se-ejecuta-solo|B-002]], [[B-003-topico-kafka-queuer-no-coincide|B-003]]

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/aws/SecretManager.java`
- `queuer_ms/deployment/acceptanceTest/src/test/java/co/com/bancolombia/components/kafka/KafkaManager.java`

## Tareas
- [x] Declarar `private static final Logger LOGGER = Logger.getLogger(<Clase>.class.getName());` en `SecretManager` y `KafkaManager`.
- [x] Reemplazar los 7 `System.out.println`:
  - `info`: secreto leído, consumidor creado (bootstrap, mecanismo, group.id), truststore PEM, mensaje encontrado;
  - `warning`: timeout consultando offsets (se reintenta), mensaje no encontrado en el tiempo de espera, `certificate.cer` ilegible.
- [x] Errores: registrar con `LOGGER.log(Level.SEVERE, mensaje, e)`, conservando la causa en el log, y seguir lanzando la excepción con un mensaje claro (sin concatenar a mano `getClass().getSimpleName()` y `getMessage()`), porque Karate necesita la excepción para marcar el escenario como fallido.
- [x] No registrar nunca credenciales ni el contenido del secreto (`sasl.jaas.config`, contraseña, certificado).
- [x] Compatible con Java 8 (sin APIs posteriores) y conservar CRLF.
- [x] **Todo en inglés** (pedido del usuario el 2026-10-27): mensajes de log y de excepciones, comentarios y nombres de métodos y constantes en el código de la validación en Kafka y en lo agregado para estos endpoints: `SecretManager`, `KafkaManager`, `helpers/kafka-manager.feature`, las propiedades de Kafka y los mensajes de `karate-config.js`, los comentarios de `build.gradle` y `TestParallel`, y los comentarios de `campaigns_acceptance_test.feature` y `notifications_acceptance_test.feature`. Ejemplos: `offsetsForTimesConReintentos` → `offsetsForTimesWithRetries`, `OFFSETS_MAX_INTENTOS` → `OFFSETS_MAX_ATTEMPTS`.
- [x] Fuera de alcance: los README y la documentación del vault siguen en español; los datos de prueba (`data/*.json`) no cambian.

## Criterios de aceptación
- [x] No queda `System.out` ni `System.err` en `src/test/java` de `acceptanceTest`.
- [x] No quedan textos en español en los archivos de código listados.
- [x] `compileTestJava` compila con JDK 8 (Docker `eclipse-temurin:8-jdk`) y con JDK 21.
- [x] Ante un fallo (secreto sin credenciales, offsets sin red) el log muestra el mensaje con nivel y causa, y el escenario sigue fallando con un mensaje claro.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
grep -rn "System.out\|System.err" src/test/java   # sin resultados
java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain clean compileTestJava
docker run --rm -v "$PWD":/w -w /w eclipse-temurin:8-jdk sh -c 'java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain --no-daemon -q clean compileTestJava'
# Sin red ni credenciales (jshell/Karate del scratchpad): el error del secreto y los reintentos de offsets aparecen con nivel SEVERE/WARNING
```

## Notas
- La suite configura logback (`logback-test.xml`) para Karate. `java.util.logging` no pasa por logback: sus mensajes salen por la consola (stderr) con el formato de JUL y no quedan en `target/karate.log`. Es lo que pidió el usuario ("logger de java"); si se quisieran en `karate.log`, la alternativa sería SLF4J, que ya está en el classpath por Karate.
- 2026-10-27 — Ejecutado en `feature/7978702_queuer_acceptance_tests`. Sin commit. El usuario había quitado los comentarios de las clases y pidió no agregar ninguno: se respetó, y se quitaron los dos que quedaban en `KafkaManager` y los comentarios propios en español de `build.gradle`.
- `SecretManager` y `KafkaManager`: `java.util.logging.Logger` (`info`, `warning`, `severe` y `log(Level.SEVERE, msg, e)`), sin `System.out`. Mensajes, nombres (`offsetsForTimesWithRetries`, `OFFSETS_MAX_ATTEMPTS`, `attempt`) y excepciones en inglés; las excepciones se siguen lanzando para que Karate marque el escenario, ya sin concatenar a mano clase y mensaje de la causa (la causa va en el log y en `getCause()`).
- `karate-config.js` (`effective baseUrl`, `Kafka validation`, `... or -DkafkaValidate=false`), `helpers/kafka-manager.feature` (nombre del feature, `karate.fail`, `karate.log`) y README (`effective baseUrl: ...`) en inglés.
- Se mantienen en español solo los mensajes que devuelve el microservicio y que los escenarios comparan (`"El objeto 'metadata' es obligatorio"`, etc.): son el contrato real de la API.
- Verificación: sin `System.out`/`System.err` en `src/test/java`; `compileTestJava` OK con JDK 8 (Docker `eclipse-temurin:8-jdk`) y JDK 21; sin credenciales, `SEVERE: Could not read the Kafka secret ...` con la `SdkClientException` como causa; contra un broker inexistente, 2 `WARNING: Timeout getting the offsets ... retrying` y `SEVERE: Could not get the offsets ... after 3 attempts of 30 s`.
- Los logs de JUL salen por consola (stderr) y no en `target/karate.log` (logback).
