---
id: B-002
aliases: [B-002]
title: "El helper kafka-manager.feature se ejecuta como feature independiente y el error de lectura del secreto oculta la causa"
status: done
priority: P1
epic: E-aceptacion
estimate: S
depends_on: []
type: bug
affects: [T-026]
created: 2026-10-26
---

# B-002 — El helper `kafka-manager.feature` se ejecuta como feature independiente y el error de lectura del secreto oculta la causa

## Reproducción
- **Pasos:**
  1. En Windows, con la rama `feature/7978702_queuer_acceptance_tests` y los cambios de B-001, ejecutar en `acceptanceTest`: `gradlew clean test -Dendpoint=<ext-dev>/queuer -DcognitoEndpoint=... -DclientId=... -DclientSecret=... -DkafkaAppId=others-test -DkafkaSecretName=... -DkafkaBatchTopic=... -DkafkaOnlineTopic=...` (sin `-Daws.*`).
- **Esperado:** el helper solo se ejecuta cuando lo llaman los escenarios `202`. Si no se puede leer el secreto, el error indica por qué.
- **Observado (2026-10-26 14:31, 38 escenarios, 33 pasan y 5 fallan):**
  - `helpers/kafka-manager.feature` aparece como "feature 5 of 5" y falla solo: `ReferenceError: "expectedBody" is not defined` (línea 9).
  - AC-C01, AC-C02, AC-N01 y AC-N02 reciben su `202` y fallan en el paso de Kafka: `Error leyendo el secreto de Kafka nu0284001-artemis-dev-secret-operative-eda-composicion-nmt: SdkClientException`. El mensaje solo trae el nombre de la clase y no la causa.
  - El resto pasa contra `dev` con las rutas nuevas: `/queuer` 17/17, `400`/`403`/`422` de `/campaigns` y `/notifications`, y `get-token`.

## Causa (si se conoce)
- `TestParallel` usa `Runner.path().relativeTo(getClass())` sin filtro de tags, así que ejecuta **todos** los features de `co/com/bancolombia`, incluidos los marcados `@ignore`. Pasa igual con `get-token.feature`, que corre como feature propio (por eso el total era 37 y no 36). `get-token` no necesita argumentos y pasa; el helper sí los necesita y falla. En T-026 se asumió que `@ignore` lo excluía. La prueba del scratchpad ejecutaba solo `check.feature` y no lo detectó. `transcribe_ms` usa `.tags("~@ignore")` en su runner.
- `SecretManager` arma el mensaje con `e.getClass().getSimpleName()`, que oculta la causa (por ejemplo, "Unable to load credentials from any of the providers in the chain"). Los mensajes del SDK no incluyen el valor del secreto, así que se pueden mostrar.
- La `SdkClientException` en sí es esperable en local: no se pasaron `-Daws.*` y no había sesión de AWS. En el release pasará lo mismo si no se agregan esas variables (riesgo anotado en [[B-001-aceptacion-no-compila-java8|B-001]]).

## Criterios de aceptación
- [x] `helpers/kafka-manager.feature` ya no se ejecuta como feature independiente.
- [x] El conteo de la suite queda documentado (con `~@ignore` también deja de correr `get-token.feature` solo: 36 escenarios = 17 `/queuer` + 10 campañas + 9 notificaciones).
- [x] Si no se puede leer el secreto, el mensaje incluye la causa del SDK (sin valores del secreto).
- [x] ~~Con credenciales AWS válidas (`-Daws.*` o sesión local), los 4 escenarios `202` validan el mensaje en Kafka en `dev`.~~ Movido a [[B-003-topico-kafka-queuer-no-coincide|B-003]]: con credenciales el secreto se lee y el consumidor conecta; los fallos restantes no son de este bug.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
# Regresion: hoy el reporte incluye "helpers/kafka-manager.feature" como feature ejecutado; tras el fix no aparece
./gradlew clean test -Dendpoint=... -DkafkaValidate=false ... | grep -E "feature:|scenarios:"
# Sin credenciales AWS: el error debe mostrar la causa del SDK
./gradlew clean test -Dendpoint=... -DkafkaSecretName=... -DkafkaBatchTopic=... -DkafkaOnlineTopic=... | grep "Error leyendo el secreto"
# Con credenciales (dev): 36/36
./gradlew clean test ... -Daws.accessKeyId=... -Daws.secretKey=... -Daws.sessionToken=...
```

## Notas
- **Fix propuesto:**
  - `TestParallel.java`: agregar `.tags("~@ignore")` al `Runner`, como `transcribe_ms`. Alternativa menos invasiva: en el helper, `* if (typeof expectedBody == 'undefined') karate.abort()` al inicio, que mantiene `get-token` como feature ejecutado (37). Se recomienda `~@ignore` porque es el uso estándar del tag.
  - `SecretManager.java`: en el `catch`, incluir `e.getMessage()` además de la clase.
  - Revisar si el README o `docs/pruebas.md` citan el total 37 y actualizarlo.
- **Configuración (no es código, la hace el usuario):** para que la validación en Kafka funcione hay que pasar credenciales AWS con permiso de lectura del secreto:
  - en local, `-Daws.accessKeyId`, `-Daws.secretKey`, `-Daws.sessionToken` o una sesión de AWS activa;
  - en el release, esas mismas variables (secretas) en la tarea de aceptación.

  Mientras tanto, `-DkafkaValidate=false` deja correr la suite sin Kafka.
- La corrida local confirma que T-021 y T-022 funcionan contra `dev`: las rutas `/campaigns` y `/notifications` responden como se espera.
- 2026-10-26 — Ejecutado en `feature/7978702_queuer_acceptance_tests`. Sin commit.
- Regresión (antes del fix): corrida local con endpoints a `localhost` y `-DkafkaValidate=false`; el resumen de Karate lista 5 features y 38 escenarios, incluidos `get-token.feature` (1) y `helpers/kafka-manager.feature` (1).
- Fix: `TestParallel` con `.tags("~@ignore")` y comentario; en `SecretManager`, el `catch` agrega `e.getMessage()` a la clase de la excepción. CRLF conservado.
- Después del fix, misma corrida: 3 features y 36 escenarios (17 `/queuer` + 9 notificaciones + 10 campañas); `get-token` y el helper solo se ejecutan cuando los llaman (`callonce` / `karate.call`).
- Mensaje sin credenciales (feature temporal del scratchpad, sin variables ni perfil de AWS): `Error leyendo el secreto de Kafka secreto-inexistente-qa: SdkClientException - Unable to load credentials from any of the providers in the chain AwsCredentialsProviderChain(...)`. No incluye valores del secreto.
- Conteo 37 → 36 actualizado en T-022, T-026 y T-027. README y `docs/pruebas.md` no citaban el total.
- **blocked:** falta la corrida en `dev` con credenciales AWS y VPN para el último criterio (los 4 `202` validan en Kafka). La corrida del usuario de las 14:41 falló por `UnknownHostException` del host de `dev` (red/VPN), no por el código.
- 2026-10-26 14:53 — Corrida del usuario en Windows con credenciales AWS: 3 features, 36 escenarios (`skipped: 2`), 32 pasan. El helper ya no corre solo. Los 4 fallos son de Kafka: DNS local y tópico sin el mensaje (ver B-003). Se cierra en `done`.
