---
id: T-017
aliases: [T-017]
title: "Escenarios E2E de notificaciones en línea por el queuer (WhatsApp y Teams)"
status: done
priority: P1
epic: E-e2e
estimate: S
depends_on: [T-016]
type: task
created: 2026-10-22
---

# T-017 — Escenarios E2E de notificaciones en línea por el queuer (WhatsApp y Teams)

## Objetivo
Crear la suite `Queuer` con los escenarios de notificación en línea: enviar por `POST /notifications` y verificar en el fakechannel que el usuario recibió exactamente el texto enviado.

## Documentación relacionada
- [Contrato de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md)
- Suite de referencia: `Platform_test/src/test/resources/features/notifications.feature`
- [Observación 1 — casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata): el queuer publica `NotificationEvent` con `metadata` en camelCase; la suite `Notifications` publica en PascalCase.

## Archivos a crear/modificar
`Platform_test/`:
- `src/test/resources/features/queuer.feature` (nuevo)
- `src/test/java/.../runners/Queuer.java` (nuevo; copia de `Notifications.java` con `features/queuer.feature`)

## Tareas
- [x] Crear el feature con `@UserStory=#{user-story}#` en cada escenario, como el resto:

```gherkin
Feature: Validate queuer Kafka REST proxy end-to-end flow
  As an IT User
  I want to send events through the queuer REST proxy
  So I can validate they are delivered by the Chatbots Platform

  @UserStory=#{user-story}#
  Scenario: Queuer online notification E2E WhatsApp flow
    Given I prepare the whatsapp notification event
    When I obtain the Cognito access token
    And I send the notification event through the queuer
    Then the queuer should accept the event
    And I verify the notification was delivered successfully

  @UserStory=#{user-story}#
  Scenario: Queuer online notification E2E TEAMS flow
    Given I prepare the teams notification event
    When I obtain the Cognito access token
    And I send the notification event through the queuer
    Then the queuer should accept the event
    And I verify the notification was delivered successfully
```

- [x] Crear el runner `Queuer.java`.

## Criterios de aceptación
- [x] Los 2 escenarios pasan en QA, o fallan por un defecto confirmado que queda registrado como bug `B-0NN` con `affects` a esta tarjeta. Ejemplo: el consumidor no deserializa `metadata` por la observación 1.
- [x] Los escenarios no usan `-DonlineNotificationTopic` ni `-DkafkaSecretName`: la publicación es responsabilidad del queuer.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test
./gradlew clean test --tests "co.com.bancolombia.certification.chatbotsPlatform.runners.Queuer" \
  -Denvironment=qa -DappId=others-test \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  -DendpointQueuer="$ENDPOINT_QUEUER" -DendpointGetMessageFake="$ENDPOINT_FAKE" --info \
  | grep -E "Scenario|PASSED|FAILED|tests completed"
```

## Notas
- `VerifyChannelDelivery` reintenta 5 veces cada 10 s. Si el queuer tarda por reintentos de Kafka ([observación 5](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)), el fallo aparecerá antes, en `the queuer should accept the event`.
- 2026-10-29 — Creados `features/queuer.feature` (los 2 escenarios de la tarjeta) y `runners/Queuer.java` (copia de `Notifications.java` apuntando a `features/queuer.feature`) en la rama `feature/7999754-e2e-tests-campaigns-notifications-queuer`, sobre el commit de [[T-016-interaccion-envio-queuer|T-016]] (`c410a27`). `./gradlew compileTestJava` → OK.
- 2026-10-29 — Ejecución local contra QA, con aprobación del usuario (`-DappId=others-test`, `-DendpointQueuer=https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/queuer/v1`, sin `-DonlineNotificationTopic` ni `-DkafkaSecretName`): `BUILD SUCCESSFUL`, Serenity 2 escenarios, 2 pasados, 0 fallidos (33,9 s).
  - WhatsApp: usuario `572636215916`, mensaje `Notif_e2e_test_573eea9f` → `202 accepted`; entregado en el fakechannel en el intento 1.
  - Teams: usuario `sepiedra@ambientesbc.com`, `conversationId` `27060555-ecc0-4aad-85b6-9a663cd04331`, mensaje `Notif_e2e_test_07e83c57` → `202 accepted`; entregado en el intento 2 (unos 10 s más).
  - El token sale enmascarado (`Bearer ****`) en los logs de la suite y el reporte `target/site/serenity` no contiene el `clientSecret`. Con `--info`, Gradle sí imprime la línea de comando del JVM de test con todas las `-D`, incluido `-DclientSecret`: es comportamiento de Gradle, no de la suite. Al compartir evidencias, no usar `--info` o enmascarar esa línea ([[T-020-ejecucion-e2e-qa|T-020]]).
- El estado de E2E-N01 / E2E-N02 en `docs/pruebas.md` se actualiza con la ejecución desde el release en [[T-020-ejecucion-e2e-qa|T-020]].
