---
id: B-004
aliases: [B-004]
title: "La suite de aceptación no compila en el agente: --release no existe en javac de JDK 8"
status: blocked
priority: P0
epic: E-aceptacion
estimate: S
depends_on: []
type: bug
affects: [T-026]
created: 2026-10-26
---

# B-004 — La suite de aceptación no compila en el agente: `--release` no existe en `javac` de JDK 8

## Reproducción
- **Pasos:**
  1. Release de `queuer_ms` en `dev` con la rama que incluye [[B-001-aceptacion-no-compila-java8|B-001]], [[B-002-helper-kafka-se-ejecuta-solo|B-002]] y [[B-003-topico-kafka-queuer-no-coincide|B-003]]; tarea `gradlew build` de aceptación (2026-10-26 20:59).
- **Esperado:** `compileTestJava` compila con el JDK 8 del agente y la suite se ejecuta.
- **Observado:**

```
Compiling with toolchain '/usr/lib/jvm/java-8-openjdk-amd64'.
> Task :compileTestJava FAILED
Execution failed for task ':compileTestJava'.
> invalid flag: --release
```

## Causa (si se conoce)
- B-001 agregó en `build.gradle` `tasks.withType(JavaCompile).configureEach { options.release = 8 }` para que la compilación local (JDK 21) tuviera la misma restricción que el agente. `--release` existe desde `javac` 9, así que el `javac` de JDK 8 del agente lo rechaza. En local no se detectó porque WSL y Windows compilan con JDK 21. La verificación de B-001 no contempló que el agente usa el mismo `build.gradle`.

## Criterios de aceptación
- [x] `options.release = 8` se aplica solo si el JDK que compila es 9 o superior (`JavaVersion.current().isJava9Compatible()`). Con JDK 8 no se pasa la opción: ese compilador ya produce bytecode 52 y solo tiene la API de Java 8.
- [x] En local (JDK 21), `compileTestJava` sigue fallando si se usa una API posterior a Java 8 (protección de B-001 intacta).
- [ ] En el agente (JDK 8), `compileTestJava` compila y la suite se ejecuta.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
# Regresion con un JDK 8 local (por ejemplo, una imagen eclipse-temurin:8): falla hoy con "invalid flag: --release" y compila tras el fix
docker run --rm -v "$PWD":/w -w /w eclipse-temurin:8-jdk sh -c 'java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain clean compileTestJava'
# Proteccion local con JDK 21: un isBlank() temporal debe seguir fallando
java -cp gradle/wrapper/gradle-wrapper.jar org.gradle.wrapper.GradleWrapperMain clean compileTestJava
```

## Notas
- **Configuración del release (no es código; la hace el usuario):** en el mismo log, el comando llega con `-Daws.accessKeyId=$(AWS_ACCESS_KEY_ID) -Daws.secretKey=$(AWS_SECRET_ACCESS_KEY) -Daws.sessionToken=$(AWS_SESSION_TOKEN)` **literales**. Azure DevOps deja `$(NOMBRE)` sin reemplazar cuando la variable no existe en el release ni en sus variable groups (si existiera y fuera secreta, se vería `***`, como `clientSecret`). Hay que crear las variables con esos nombres exactos, o usar en el comando los nombres que ya existan (por ejemplo, los del release de `transcribe_ms` o `platform_campaigns_ms`). Si no, cuando compile, `SecretManager` fallará con credenciales inválidas.
- La verificación local con JDK 8 requiere una imagen con JDK 8 o un JDK 8 instalado. Si no está disponible, se valida directamente en el release.
- 2026-10-26 — Ejecutado en `feature/7978702_queuer_acceptance_tests`. Sin commit.
- Regresión con JDK 8 real (`docker run eclipse-temurin:8-jdk`, `openjdk 1.8.0_504`, mismo proyecto montado): antes del fix, `compileTestJava` falla con `invalid flag: --release`, igual que en el agente.
- Fix en `build.gradle`: `options.release = 8` solo dentro de `if (JavaVersion.current().isJava9Compatible())`, con comentario. CRLF conservado.
- Después del fix: con JDK 8 (Docker), `clean compileTestJava` termina con código 0. Con JDK 21 (WSL), en una copia del proyecto en el scratchpad, un `isBlank()` temporal sigue fallando con `cannot find symbol` y sin él compila: la protección de B-001 se mantiene.
- **blocked:** falta el release en `dev` (criterio "en el agente compila y la suite se ejecuta").
- Seguridad: en el release de las 21:35 las variables `AWS_*` no estaban marcadas como secretas y sus valores quedaron en texto plano en el log. Se pidió al usuario marcarlas como secretas e invalidar o rotar esas credenciales.
