---
id: T-018
aliases: [T-018]
title: "Escenarios E2E de campañas por el queuer (WhatsApp y Teams)"
status: done
priority: P1
epic: E-e2e
estimate: M
depends_on: [T-016]
type: task
created: 2026-10-22
---

# T-018 — Escenarios E2E de campañas por el queuer (WhatsApp y Teams)

## Objetivo
Agregar a `queuer.feature` los escenarios de campaña: enviar un `initiatecampaign` por `POST /campaigns` y verificar en el fakechannel que el usuario recibió el texto del nodo de campaña. Es lo mismo que valida hoy la suite `Campaigns`, pero sin pasar por CSV, S3 ni Lambda.

## Documentación relacionada
- [Contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Observación 1 — casing de `metadata`](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)
- [[T-015-prerrequisitos-e2e-qa|T-015]]: qué identificadores y nodo acepta el consumidor.

## Archivos a crear/modificar
- `Platform_test/src/test/resources/features/queuer.feature`
- No hace falta un paso de verificación nuevo: `I verify the campaign was delivered successfully` ya existe (`VerifyCampaignDelivery` + `CheckCampaignResponse`) y se reutiliza sin cambios. El `CampaignMemory.reset()` en `@Before` lo agrega [[T-016-interaccion-envio-queuer|T-016]].

## Tareas
- [x] Agregar los escenarios:

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

- [x] Hacer que `PrepareQueuerCampaignEvent` deje en `CampaignMemory` lo que necesita `VerifyCampaignDelivery`: canal (`csvCanal`), usuario de verificación y `expectedBody`. Así se reutiliza el paso existente sin cambiarlo. Si `expectedBody` queda vacío, `VerifyCampaignDelivery` lo toma del dataset por defecto, así que hay que fijarlo siempre.

## Criterios de aceptación
- [x] Los 2 escenarios pasan en QA, o fallan por un defecto confirmado que queda registrado como bug `B-0NN` con `affects` a esta tarjeta. Ejemplo: el consumidor no deserializa `metadata` por la observación 1.
- [x] La suite `Campaigns` existente no cambia.

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
- 2026-10-29 — Agregados los 2 escenarios de campaña a `queuer.feature`. `PrepareQueuerCampaignEvent` ahora también llena `CampaignMemory` (`csvCanal`, `generatedUser`, `verificationUser` y `expectedBody`, siempre fijado desde el dataset), así que `I verify the campaign was delivered successfully` se reutiliza sin cambios. `campaigns.feature`, `VerifyCampaignDelivery` y `CampaignMemory` no se tocaron. `./gradlew compileTestJava` → OK.
- 2026-10-29 — Ejecución local del runner `Queuer` completo contra QA, con aprobación del usuario (mismas `-D` que [[T-017-e2e-notificaciones-queuer|T-017]], sin `--info` para que Gradle no imprima `-DclientSecret`): `BUILD SUCCESSFUL`, JUnit `tests="4" failures="0" errors="0"`. Los 4 escenarios recibieron `202 accepted` y se entregaron en el intento 1.
  - Campaña WhatsApp: usuario `573665317168`, `campaign.identifier` `6d1965fb-7c53-417c-84e8-19c9bdc3389d`, nodo `N-03-99-10` → `Campaig_e2e_test_delivered_successfully` en el fakechannel.
  - Campaña Teams: usuario `sepiedra@ambientesbc.com`, `conversationId` `27060555-ecc0-4aad-85b6-9a663cd04331`, `campaign.identifier` `c33ee9b3-8681-4588-8d52-e2c9e21deb67` → mismo texto, 1 s después del `202`.
  - En Teams el texto y el `conversationId` son fijos, así que una entrega vieja podría dar un falso positivo. `get-messages` devuelve solo el último mensaje: en la lectura anterior (notificación Teams de la misma corrida) el último era `Notif_e2e_test_abcc01bc` y en esta era el de la campaña, así que la entrega es de esta ejecución. Si el escenario de campaña Teams se corre aislado, esa garantía no existe.
