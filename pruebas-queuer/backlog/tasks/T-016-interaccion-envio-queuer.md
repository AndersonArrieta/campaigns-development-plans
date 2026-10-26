---
id: T-016
aliases: [T-016]
title: "Interacción Screenplay para enviar eventos por el queuer y validar el 202"
status: backlog
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
- `src/test/resources/jsons/queuerNotificationEvent.json` y `queuerCampaignEvent.json` (nuevos; `metadata` en PascalCase)
- `src/test/java/.../stepdefinitions/EngineAdapterStepDefinition.java`: pasos nuevos y `QueuerMemory.reset()` en `@Before`.

## Tareas
- [ ] Crear `SendEventThroughQueuer.notifications()` / `.campaigns()`:
  - hace un POST con Unirest a `System.getProperty("endpointQueuer") + "/notifications"` o `"/campaigns"` con `Authorization: Bearer ExecutionMemory.getCognitoAC()`;
  - si falta `-DendpointQueuer`, lanza `GeneralException`;
  - guarda status y body en `QueuerMemory`.
- [ ] Para notificaciones, reutilizar `PrepareNotificationEvent`: usuario, mensaje único y `appId`. Crear `PrepareQueuerCampaignEvent`, que lee `campaigns_e2e_flow` del dataset (nodo y `expectedBody`) y genera `campaign.identifier` y `notification.identifier` según [[T-015-prerrequisitos-e2e-qa|T-015]].
- [ ] Crear `CheckQueuerAccepted`, que responde `success` solo si `status == 202` y `body.status == "accepted"`. Si no, responde `fail - HTTP <code> <body>`.
- [ ] Agregar los pasos, en el estilo de los existentes:
  - `Given I prepare the (.*) campaign event for the queuer` (`whatsapp` / `teams`)
  - `When I send the notification event through the queuer`
  - `When I send the campaign event through the queuer`
  - `Then the queuer should accept the event`
- [ ] Antes de loguear, enmascarar el token y el `clientSecret` con `LogMasker`.

## Criterios de aceptación
- [ ] `./gradlew clean build -x test` compila sin errores.
- [ ] Las suites existentes (`Notifications`, `Campaigns`, `IntegratorNode`) no cambian de comportamiento: no se modificaron sus pasos.
- [ ] No hay credenciales ni hosts de QA escritos en el código; todo llega por `-D`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test
./gradlew clean build -x test
grep -rn -E 'informacion-.*ambientesbc|clientSecret *= *"' src/main src/test/java | grep -v getProperty || echo "sin valores fijos"
git diff --stat
```

## Notas
- Rama en el repo `_MR_Test` desde `trunk`. Commits con convención `feat(queuer_ms_test): ...`. Los commits y el push requieren confirmación del usuario.
