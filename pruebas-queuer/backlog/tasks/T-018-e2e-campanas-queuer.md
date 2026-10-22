---
id: T-018
aliases: [T-018]
title: "Escenarios E2E de campañas por el queuer (WhatsApp y Teams)"
status: backlog
priority: P1
epic: E-e2e
estimate: M
depends_on: [T-016]
type: task
created: 2026-10-22
---

# T-018 — Escenarios E2E de campañas por el queuer (WhatsApp y Teams)

## Objetivo
Agregar a `queuer.feature` los escenarios de campaña: enviar un `initiatecampaign` por `POST /api/v1/campaigns` y verificar en el fakechannel que el usuario recibió el texto del nodo de campaña. Es lo mismo que valida hoy la suite `Campaigns`, pero sin pasar por CSV, S3 ni Lambda.

## Documentación relacionada
- [Contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Observación 1 — casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)
- [[T-015-prerrequisitos-e2e-qa|T-015]]: qué identificadores y nodo acepta el consumidor.

## Archivos a crear/modificar
- `Platform_test/src/test/resources/features/queuer.feature`
- Si hace falta un paso de verificación propio para campañas: `EngineAdapterStepDefinition.java`, reutilizando `VerifyChannelDelivery` con el `expectedBody` de `campaigns_e2e_flow`.

## Tareas
- [ ] Agregar los escenarios:

```gherkin
  @UserStory=#{user-story}#
  Scenario: Queuer campaign E2E WhatsApp flow
    Given I prepare the whatsapp campaign event for the queuer
    When I obtain the Cognito access token
    And I send the campaign event through the queuer
    Then the queuer should accept the event
    And I verify the campaign was delivered successfully

  @UserStory=#{user-story}#
  Scenario: Queuer campaign E2E TEAMS flow
    Given I prepare the teams campaign event for the queuer
    When I obtain the Cognito access token
    And I send the campaign event through the queuer
    Then the queuer should accept the event
    And I verify the campaign was delivered successfully
```

- [ ] Hacer que `PrepareQueuerCampaignEvent` deje en `CampaignMemory` lo que necesita `VerifyCampaignDelivery`: canal, usuario de verificación y `expectedBody`. Así se reutiliza el paso existente sin cambiarlo.

## Criterios de aceptación
- [ ] Los 2 escenarios pasan en QA, o fallan por un defecto confirmado que queda registrado como bug `B-0NN` con `affects` a esta tarjeta. Ejemplo: el consumidor no deserializa `metadata` por la observación 1.
- [ ] La suite `Campaigns` existente no cambia.

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
- El escenario de Teams usa el `conversationId` y el usuario fijos del dataset de Teams (`campaignUser`). No cambiarlos sin confirmar con el equipo, porque los comparte con la suite `Campaigns`.
