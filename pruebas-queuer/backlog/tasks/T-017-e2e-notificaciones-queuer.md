---
id: T-017
aliases: [T-017]
title: "Escenarios E2E de notificaciones en línea por el queuer (WhatsApp y Teams)"
status: backlog
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

## Archivos a crear/modificar
`Platform_test/`:
- `src/test/resources/features/queuer.feature` (nuevo)
- `src/test/java/.../runners/Queuer.java` (nuevo; copia de `Notifications.java` con `features/queuer.feature`)

## Tareas
- [ ] Crear el feature con `@UserStory=#{user-story}#` en cada escenario, como el resto:

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

- [ ] Crear el runner `Queuer.java`.

## Criterios de aceptación
- [ ] Los 2 escenarios pasan en QA.
- [ ] Los escenarios no usan `-DonlineNotificationTopic` ni `-DkafkaSecretName`: la publicación es responsabilidad del queuer.

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
