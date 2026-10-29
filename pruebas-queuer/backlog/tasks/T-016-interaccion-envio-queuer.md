---
id: T-016
aliases: [T-016]
title: "Interacción Screenplay para enviar eventos por el queuer y validar el 202"
status: done
priority: P1
epic: E-e2e
estimate: M
depends_on: [T-015]
type: task
created: 2026-10-22
---

# T-016 — Interacción Screenplay para enviar eventos por el queuer y validar el `202`

## Objetivo
Agregar a `Platform_test` las piezas reutilizables para que una suite E2E envíe un evento de notificación o de campaña a `POST /notifications` o `POST /campaigns` del queuer con el token de Cognito, y compruebe el `202 accepted`. Deben seguir el estilo de `PublishNotificationEvent` / `CheckNotificationPublished`.

## Documentación relacionada
- [Contrato de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md)
- [Contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md)

## Archivos a crear/modificar
Repo `NU0284001_Artemis_Chatbots_Platform_MR_Test`, carpeta `Platform_test/`:
- `src/main/java/.../interactions/SendEventThroughQueuer.java` (nuevo)
- `src/main/java/.../interactions/PrepareQueuerCampaignEvent.java` (nuevo)
- `src/main/java/.../models/QueuerMemory.java` (nuevo): ruta, `metadata.Id`, HTTP status y body de respuesta, y datos de la campaña.
- `src/main/java/.../questions/queuer/CheckQueuerAccepted.java` (nuevo)
- `src/test/resources/jsons/queuerCampaignEvent.json` (nuevo; `metadata` en PascalCase). Para notificaciones se reutiliza `onlineNotificationEvent.json`, que ya cumple el contrato del queuer.
- `src/test/java/.../stepdefinitions/EngineAdapterStepDefinition.java`: pasos nuevos, y `QueuerMemory.reset()` y `CampaignMemory.reset()` en `@Before`. Hoy el `@Before` solo resetea `NotificationMemory`.

## Tareas
- [x] Crear `SendEventThroughQueuer.notifications()` / `.campaigns()`:
  - hace el POST con `RestServices.getConsumePostService(...)` (ya enmascara headers y body con `LogMasker`) a `System.getProperty("endpointQueuer") + "/notifications"` o `"/campaigns"` con `Authorization: Bearer ExecutionMemory.getCognitoAC()`;
  - antes del POST, configura Unirest con el mismo cliente SSL de `VerifyChannelDelivery.configureUnirestSsl()`. Si se extrae a un util compartido, `VerifyChannelDelivery` debe seguir haciendo lo mismo;
  - si falta `-DendpointQueuer`, lanza `GeneralException`;
  - guarda status y body en `QueuerMemory`.
- [x] Para notificaciones, reutilizar `PrepareNotificationEvent` (usuario, mensaje único y `appId`) y armar el body desde `onlineNotificationEvent.json` igual que `PublishNotificationEvent.buildPayload()`. Si ese armado se extrae a un util, `PublishNotificationEvent` no cambia de comportamiento. Crear `PrepareQueuerCampaignEvent`, que lee `campaigns_e2e_flow` del dataset (nodo y `expectedBody`) y genera `campaign.identifier` y `notification.identifier` según [[T-015-prerrequisitos-e2e-qa|T-015]].
- [x] Crear `CheckQueuerAccepted`, que responde `success` solo si `status == 202` y `body.status == "accepted"`. Si no, responde `fail - HTTP <code> <body>`.
- [x] Agregar los pasos, en el estilo de los existentes:
  - `Given I prepare the (.*) campaign event for the queuer` (`whatsapp` / `teams`)
  - `When I send the notification event through the queuer`
  - `When I send the campaign event through the queuer`
  - `Then the queuer should accept the event`
- [x] No loguear el token ni el `clientSecret` fuera de `RestServices` / `LogMasker`. Lo que se loguee aparte, como el body de respuesta en `CheckQueuerAccepted`, pasa por `LogMasker.mask`.

## Criterios de aceptación
- [x] `./gradlew clean build -x test` compila sin errores.
- [x] Las suites existentes (`Notifications`, `Campaigns`, `IntegratorNode`) no cambian de comportamiento: no se modificaron sus pasos.
- [x] No hay credenciales ni hosts de QA escritos en el código; todo llega por `-D`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test
./gradlew clean build -x test
grep -rn -E 'informacion-.*ambientesbc|clientSecret *= *"' src/main src/test/java | grep -v getProperty || echo "sin valores fijos"
git diff --stat
```

## Notas
- Antes de crear la rama: el `trunk` local de `_MR_Test` tiene unos 284 archivos modificados con las mismas líneas añadidas y quitadas (fin de línea CRLF, sin cambios reales) y su último commit es del 2026-10-20. Hay que limpiar ese estado (descarta cambios locales, así que requiere confirmación del usuario) y hacer `git pull`; si no, el `git diff --stat` de la verificación queda lleno de ruido.
- Rama en el repo `_MR_Test` desde `trunk`. Commits con convención `feat(queuer_ms_test): ...`. Los commits y el push requieren confirmación del usuario.
- 2026-10-29 — Rama `feature/7999754-e2e-tests-campaigns-notifications-queuer` (ya creada, en el mismo commit que `origin/trunk`, `85b065c`). Los 284 archivos modificados eran solo fin de línea: con `git -c core.autocrlf=true status` el árbol queda limpio, así que no se descartó nada. Para revisar el diff sin ruido: `git -c core.autocrlf=true diff --stat`.
- 2026-10-29 — Implementado en `Platform_test`:
  - `models/QueuerMemory`, `interactions/SendEventThroughQueuer` (`.notifications()` / `.campaigns()`), `interactions/PrepareQueuerCampaignEvent`, `questions/queuer/CheckQueuerAccepted` y `jsons/queuerCampaignEvent.json`.
  - `EngineAdapterStepDefinition`: 4 pasos nuevos y `CampaignMemory.reset()` + `QueuerMemory.reset()` en `@Before`. Los escenarios de `campaigns.feature` arman su `CampaignMemory` dentro de cada escenario, así que el reset no les afecta.
  - El cliente SSL y el armado del payload de notificación se copiaron en `SendEventThroughQueuer` en lugar de extraerlos a un util: así `VerifyChannelDelivery` y `PublishNotificationEvent` no cambian.
  - `PrepareQueuerCampaignEvent` siempre envía `node` (del dataset), `retries` = `0` y `campaign.identifier` / `notification.identifier` como UUID, que exige `platform_campaigns_ms` ([[T-015-prerrequisitos-e2e-qa|T-015]]). Guarda en `QueuerMemory` el canal, el usuario de verificación y `expectedBody`; copiarlos a `CampaignMemory` queda para [[T-018-e2e-campanas-queuer|T-018]].
  - Si el POST falla con una respuesta no JSON (p. ej. `403 RBAC: access denied`), `RestServices` lanza `InvalidResponseException`; se captura y `CheckQueuerAccepted` responde `fail - HTTP 0 <error>`.
- 2026-10-29 — Verificación: `./gradlew clean build -x test` → `BUILD SUCCESSFUL`. Como `-x test` no compila `src/test`, también se corrió `./gradlew compileTestJava` → `BUILD SUCCESSFUL`. La búsqueda de hosts y secretos fijos da "sin valores fijos". `git -c core.autocrlf=true diff --stat`: solo `EngineAdapterStepDefinition.java` (+37) y 5 archivos nuevos. Los pasos se ejecutan por primera vez en QA con [[T-017-e2e-notificaciones-queuer|T-017]]. Sin commit (requiere confirmación del usuario).
