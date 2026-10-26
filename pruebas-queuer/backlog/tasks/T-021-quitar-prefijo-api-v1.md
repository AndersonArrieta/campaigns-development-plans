---
id: T-021
aliases: [T-021]
title: "Quitar el prefijo /api/v1 de las rutas de campaigns y notifications en RouterRest"
status: backlog
priority: P1
epic: E-entorno
estimate: S
depends_on: []
type: task
created: 2026-10-26
---

# T-021 — Quitar el prefijo `/api/v1` de las rutas de campaigns y notifications en `RouterRest`

## Objetivo
Cambio solicitado sobre `queuer_ms`: las rutas `POST /api/v1/campaigns` y `POST /api/v1/notifications` pasan a ser `POST /campaigns` y `POST /notifications`. `POST /queuer` no cambia. Los handlers (`handleCampaignRequest`, `handleNotificationRequest`), el contrato de request/response y el `accept(APPLICATION_JSON)` tampoco cambian.

El cambio rompe las pruebas ya cerradas: [[T-004-aceptacion-campaigns|T-004]], [[T-005-aceptacion-notifications|T-005]] y [[T-006-humo-endpoints-kafka|T-006]] usan `path '/api/v1/...'`. En cuanto se despliegue, esos escenarios responderán `404`. Los ajustes van en [[T-022-ajustar-aceptacion-rutas-sin-api-v1|T-022]] y [[T-023-ajustar-humo-rutas-sin-api-v1|T-023]], que **deben ir en el mismo PR** que esta tarjeta. Si no, el release de aceptación y el de humo fallan en el primer despliegue.

## Documentación relacionada
- [Contrato de campañas](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Contrato de notificaciones](../../docs/endpoints/POST-api-v1-notifications.md)
- [Endpoints nuevos y componentes](../../docs/README.md#endpoints-nuevos)
- Exposición por VirtualService: notas de [[T-002-verificar-exposicion-rutas|T-002]]

## Archivos a crear/modificar
- `queuer_ms/infrastructure/entry-points/reactive-web/src/main/java/co/com/bancolombia/api/RouterRest.java`
- `queuer_ms/infrastructure/entry-points/reactive-web/src/test/java/co/com/bancolombia/api/HandlerTest.java` (constantes `URI_CAMPAIGNS` y `URI_NOTIFICATIONS`)
- `queuer_ms/infrastructure/entry-points/reactive-web/src/test/java/co/com/bancolombia/api/RouterRestTest.java` (si se agregan pruebas de ruta)
- `pruebas-queuer/docs/`: `README.md`, `endpoints/POST-api-v1-campaigns.md`, `endpoints/POST-api-v1-notifications.md`, `pruebas.md` (secciones de contrato y curl locales)

## Tareas
- [ ] Definir la rama con el usuario. Los features que ajustan T-022 y T-023 **todavía no están en `trunk`**: viven en `feature/7978702_queuer_acceptance_tests`, que ya incluye la rama de humo por el merge `73f59c186`. Hay dos opciones: integrar esas ramas a `trunk` y crear la rama de T-021 desde `trunk`, o crearla desde `feature/7978702_queuer_acceptance_tests`. El work item también se confirma con el usuario.
- [ ] En `RouterRest`, cambiar `"/api/v1/campaigns"` → `"/campaigns"` y `"/api/v1/notifications"` → `"/notifications"`.
- [ ] En `HandlerTest`, actualizar `URI_CAMPAIGNS = "/campaigns"` y `URI_NOTIFICATIONS = "/notifications"`.
- [ ] Agregar en `RouterRestTest` (o `HandlerTest`) un caso que confirme que `POST /api/v1/campaigns` y `POST /api/v1/notifications` ya **no** están registradas (`404`), para que la regresión quede cubierta.
- [ ] Buscar otras referencias a `/api/v1` en `queuer_ms` (`grep -rn "api/v1" queuer_ms --include=*.java --include=*.yaml --include=*.md`) y ajustarlas. Hoy solo aparecen `RouterRest`, `HandlerTest`, los features y los README de `acceptanceTest`/`smokeTest`; los dos últimos son de T-022 y T-023. `docs/swagger.yaml` no documenta estas rutas.
- [ ] Confirmar con el usuario si algún consumidor ya llama `/api/v1/*` en `dev`/QA. Si existe, **detenerse**: quitar la ruta vieja es un cambio de contrato con efecto fuera de este repo.
- [ ] Actualizar `docs/` de este vault a las rutas nuevas. Se conservan los nombres de archivo `POST-api-v1-*.md` para no romper los enlaces de las tarjetas `done`; el título y la fila `Ruta` se actualizan, con una nota de que la ruta anterior era `/api/v1/...` hasta T-021.
- [ ] Ajustar las tarjetas **no `done`** que citan `/api/v1/*`: [[T-008-exposicion-rutas-qa|T-008]], [[T-009-datos-carga-kafka-qa|T-009]], [[T-011-carga-campaigns-jmeter|T-011]], [[T-012-carga-notifications-jmeter|T-012]], [[T-015-prerrequisitos-e2e-qa|T-015]], [[T-016-interaccion-envio-queuer|T-016]], [[T-017-e2e-notificaciones-queuer|T-017]] y [[T-018-e2e-campanas-queuer|T-018]], y las épicas `E-entorno`, `E-aceptacion`, `E-humo`, `E-modular` y `E-e2e`. Las tarjetas `done` no se tocan.
- [ ] Desplegar en `dev` y verificar con curl (bloque `## Verificación`).

## Criterios de aceptación
- [ ] `./gradlew clean test` del microservicio pasa, incluida la cobertura de `reactive-web`.
- [ ] En `dev`, con token válido y body sin `metadata`, `POST /campaigns` y `POST /notifications` responden `400 {"error":"El objeto 'metadata' es obligatorio"}`.
- [ ] En `dev`, `POST /api/v1/campaigns` y `POST /api/v1/notifications` responden `404`.
- [ ] En `dev`, sin token, las rutas nuevas responden `403 RBAC: access denied`. La `AuthorizationPolicy` no depende del path.
- [ ] `POST /queuer` sigue respondiendo igual (lo cubre la suite de aceptación existente en T-022).
- [ ] El PR incluye los cambios de T-022 y T-023.

## Verificación
```bash
# Local: solo compilación y pruebas unitarias. No valida las rutas expuestas.
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms
./gradlew clean test

# dev (con la rama desplegada): esta es la validación que cierra la tarjeta
source /mnt/c/Users/AndersonElitArrietaR/OneDrive\ -\ FINAIPRO\ TECHNOLOGIES\ SAS/Documentos/campaigns-development-plans/queuer-cognito-recipe-test/config.env
URL_EXT="$SCHEME://$GW_EXT$PREFIX_EXT"
TOKEN=$(curl -s -X POST "${COGNITO_URL%/}/oauth2/token" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=client_credentials --data-urlencode client_id="$CLIENT_ID" \
  --data-urlencode client_secret="$CLIENT_SECRET" | jq -r .access_token)

# Body sin "metadata": corta en la validacion y no publica en Kafka
BODY_C='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","campaign":{"identifier":"x","notification":{"identifier":"x","dataTime":"x"}}}}'
BODY_N='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","notification":{"identifier":"x","dataTime":"x","message":"x"}}}'

for pair in "/campaigns|$BODY_C" "/notifications|$BODY_N"; do
  p="${pair%%|*}"; b="${pair#*|}"
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT$p" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$b"         # 400 metadata
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT$p" -H 'Content-Type: application/json' -d "$b"                                        # 403
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT/api/v1$p" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$b" # 404
done
```

## Notas
- **Solo se valida en `dev`.** Las rutas, Istio y Cognito no se pueden probar en local. En local solo se comprueba que compila y que pasan las pruebas unitarias (`./gradlew clean test`). La tarjeta se cierra cuando la rama está desplegada en `dev` y pasan los curl, la suite de aceptación de T-022 y la de humo de T-023. Los tres se validan con un solo despliegue. Si la rama aún no está desplegada, la tarjeta queda en `blocked` con esa nota.
- Es un cambio en el microservicio, no en las pruebas. Se registra aquí porque impacta directamente las suites de este backlog.
- No hace falta cambiar el VirtualService. Según las notas de T-002, el prefijo externo `/artemis/platform/queuer/v1` se reescribe a la raíz del servicio, así que `/campaigns` y `/notifications` llegan al pod igual que `/queuer`. La `baseUrl` de Karate (`endpoint` sin `/queuer` o sin `/actuator/health`) tampoco cambia.
- Riesgo: la URL externa queda como `.../queuer/v1/campaigns`. La versión la sigue dando el prefijo del gateway, no la ruta del servicio.
