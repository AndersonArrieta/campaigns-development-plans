---
id: B-001
aliases: [B-001]
title: "La suite de aceptación no compila en el release: kafka-clients 4.1.0 e isBlank() requieren Java 11 y el agente usa Java 8"
status: blocked
priority: P0
epic: E-aceptacion
estimate: S
depends_on: []
type: bug
affects: [T-026, T-027]
created: 2026-10-26
---

# B-001 — La suite de aceptación no compila en el release: `kafka-clients 4.1.0` e `isBlank()` requieren Java 11 y el agente usa Java 8

## Reproducción
- **Pasos:**
  1. Crear un release de `queuer_ms` con la rama `feature/7978702_queuer_acceptance_tests` y ejecutar la tarea `gradlew build` de aceptación en `dev` (2026-10-26 19:10).
  2. La tarea corre `deployment/acceptanceTest/gradlew clean test ... --info` con Gradle 8.10.
- **Esperado:** `compileTestJava` compila y la suite se ejecuta (37 escenarios).
- **Observado:** falla antes de ejecutar ningún escenario:

```
Compiling with toolchain '/usr/lib/jvm/java-8-openjdk-amd64'.
KafkaManager.java:5: error: cannot access org.apache.kafka.clients.consumer.ConsumerRecord
  bad class file: .../kafka-clients-4.1.0.jar(org/apache/kafka/clients/consumer/ConsumerRecord.class)
    class file has wrong version 55.0, should be 52.0
> Task :compileTestJava FAILED
```

## Causa (si se conoce)
- El agente del release ejecuta la suite de aceptación con **Java 8** (`JAVA_VERSION=1.8.0_482`). En [[T-026-validar-mensaje-kafka-aceptacion|T-026]] se asumió JDK 21 porque es el del pipeline de build, sin revisar la tarea Gradle del release.
- `kafka-clients 4.1.0` está compilado para Java 11 (class file 55). Kafka 4.x dejó de soportar Java 8 en los clientes.
- `SecretManager.java` (líneas 24, 79 y 86) y `KafkaManager.java` (líneas 36 y 121) usan `String.isBlank()`, que es de Java 11: aunque se resuelva la librería, la compilación falla en el siguiente paso.
- En local no se detectó porque WSL compila con JDK 21 y `build.gradle` no fija `sourceCompatibility`/`release`.
- AWS SDK `2.36.0` y Karate `1.0.1` sí soportan Java 8.

## Criterios de aceptación
- [x] `compileTestJava` compila con `options.release = 8` en local (la misma restricción que el agente).
- [ ] En el release, la tarea de aceptación compila con el JDK 8 del agente y ejecuta los escenarios.
- [ ] La validación en Kafka sigue funcionando: truststore PEM desde `certificate.cer` (requiere `kafka-clients >= 2.7`), `assign()` + `offsetsForTimes()`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
# Regresion: falla hoy (kafka-clients 4.1.0 + isBlank) y pasa tras el fix
java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain clean compileTestJava
grep -rn "isBlank()" src/test/java   # sin resultados tras el fix

# dev (release nuevo con la rama): la tarea "gradlew build" de aceptacion compila y ejecuta la suite
```

## Notas
- **Opción recomendada (cambio en el repo):**
  - `build.gradle`: bajar `kafka-clients` a `3.9.1` (última línea con soporte de Java 8 en clientes) y agregar `tasks.withType(JavaCompile) { options.release = 8 }` para que la compilación local falle igual que el agente si se usa una API posterior a Java 8.
  - Reemplazar `isBlank()` por `trim().isEmpty()` en `SecretManager` y `KafkaManager`.
  - Revisar que `kafka-clients 3.9.1` no traiga CVE conocidos en el análisis de dependencias del pipeline.
- **Alternativa (cambio en el release, requiere al usuario):** configurar la tarea Gradle de aceptación del release con JDK 11 o superior (opción "JDK version" de la tarea), como probablemente hace `transcribe_ms`, que también usa `kafka-clients 4.1.0`. Afecta a toda la suite y no depende del repo.
- **Riesgo siguiente:** el comando del release no pasa `-Daws.accessKeyId`, `-Daws.secretKey` ni `-Daws.sessionToken`. `SecretManager` usará la cadena por defecto de AWS del agente; si el agente no tiene rol o credenciales, la validación en Kafka fallará al leer el secreto. Confirmarlo en la primera corrida que compile.
- Las variables `kafkaSecretName`, `kafkaBatchTopic` y `kafkaOnlineTopic` ya llegan al comando del release.
- 2026-10-26 — Ejecutado en `feature/7978702_queuer_acceptance_tests` (rama actual, por indicación del usuario). Sin commit.
- Regresión: con solo `options.release = 8` en `build.gradle`, `compileTestJava` falla en local en los 5 usos de `isBlank()` (SecretManager 24, 79, 86; KafkaManager 36, 121), igual que en el agente.
- Fix: `build.gradle` con `tasks.withType(JavaCompile).configureEach { options.release = 8 }` y `kafkaClientsVersion = "3.9.1"`; `isBlank()` → `trim().isEmpty()` en `SecretManager` y `KafkaManager`. Tras el fix, `compileTestJava` OK (solo avisos de JDK 21 por `release 8` obsoleto).
- `--release 8` no revisa el bytecode de las dependencias, así que se escanearon los 127 jars del classpath de pruebas: ninguna clase supera la versión 52 (Java 8), fuera de `META-INF/versions/`. `kafka-clients-3.9.1.jar` incluido.
- La comprobación de Karate del scratchpad (`json`, `karate.keysOf`, `contains deep`, `karate.call` condicional y `Java.type` sobre `KafkaManager`) da el mismo resultado con `kafka-clients 3.9.1`.
- **blocked:** falta un release nuevo de la rama para confirmar que la tarea de aceptación compila con el JDK 8 del agente y ejecuta la suite. Revisar ahí si `SecretManager` puede leer el secreto sin `-Daws.*` (riesgo anotado arriba) y el análisis de dependencias de `kafka-clients 3.9.1`.
