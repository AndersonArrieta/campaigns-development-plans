---
id: T-022
aliases: [T-022]
title: "Ajustar las pruebas de aceptación a /campaigns y /notifications"
status: blocked
priority: P1
epic: E-aceptacion
estimate: S
depends_on: [T-021]
affects: [T-004, T-005]
type: task
created: 2026-10-26
---

# T-022 — Ajustar las pruebas de aceptación a `/campaigns` y `/notifications`

## Objetivo
Con [[T-021-quitar-prefijo-api-v1|T-021]], `POST /api/v1/campaigns` y `POST /api/v1/notifications` pasan a ser `POST /campaigns` y `POST /notifications`. Los features de [[T-004-aceptacion-campaigns|T-004]] y [[T-005-aceptacion-notifications|T-005]] fijan `path '/api/v1/...'` en el `Background`, así que los 19 escenarios fallarían con `404`. Esta tarjeta cambia solo las rutas y los textos que las nombran. Los escenarios, payloads y aserciones siguen igual.

Va en la **misma rama y PR** que T-021.

## Documentación relacionada
- [Casos de campañas](../../docs/pruebas.md#post-apiv1campaigns)
- [Casos de notificaciones](../../docs/pruebas.md#post-apiv1notifications)
- Parametrización de `baseUrl`: [[T-001-parametrizar-karate-config|T-001]]

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/campaigns_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/notifications_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/README.md` (fila `baseUrl` de la tabla de propiedades)
- `pruebas-queuer/docs/pruebas.md` (rutas en las secciones de aceptación y en la tabla de propiedades)

## Tareas
- [x] `campaigns_acceptance_test.feature`: `path '/api/v1/campaigns'` → `path '/campaigns'` y `Feature: Acceptance Test POST /api/v1/campaigns` → `Feature: Acceptance Test POST /campaigns`.
- [x] `notifications_acceptance_test.feature`: `path '/api/v1/notifications'` → `path '/notifications'` y el nombre del `Feature` igual.
- [x] No tocar tags (`@acceptanceTest @campaigns`, `@acceptanceTest @notifications`), `karate-config.js` ni los JSON de `data/`.
- [x] README de `acceptanceTest`: en la fila `baseUrl`, "rutas `/api/v1/campaigns` y `/api/v1/notifications`" → "rutas `/campaigns` y `/notifications`".
- [x] `docs/pruebas.md`: actualizar las rutas que citan las secciones de aceptación y la tabla de propiedades. Los anclajes `#post-apiv1campaigns` y `#post-apiv1notifications` cambian si cambia el encabezado; actualizar los enlaces que los usan o conservar el encabezado con una nota.
- [x] Confirmar que no queda `/api/v1` en el proyecto: `grep -rn "api/v1" queuer_ms/deployment/acceptanceTest` sin resultados.

## Criterios de aceptación
- [ ] Con T-021 desplegada en `dev`: `--tags @campaigns` 10/10 y `--tags @notifications` 9/9.
- [ ] Suite completa de aceptación en verde: 36/36 (17 `/queuer` + 10 campañas + 9 notificaciones; desde B-002 `get-token` ya no corre como feature propio).
- [x] El release de aceptación no necesita variables nuevas: `baseUrl` se sigue derivando de `endpoint`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
grep -rn "api/v1" . --include=*.feature --include=*.md --include=*.js   # sin resultados
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" \
  -i | grep -E "scenarios|passed|failed"
```

## Notas
- **Solo se valida en `dev`.** Las suites Karate corren contra el ambiente desplegado. En local solo se revisa con `grep` que no quede `/api/v1`. La tarjeta se cierra con la suite en verde en `dev` una vez desplegada la rama de T-021. Hasta entonces queda `blocked` con esa nota.
- Si se ejecuta la suite contra `dev` **antes** de desplegar T-021, los 19 escenarios nuevos fallan con `404`: las rutas sin `/api/v1` todavía no existen. No es un defecto de las pruebas.
- T-004 y T-005 son `done` y no se editan. Esta tarjeta las enlaza con `affects`.
- Sin `-DbaseUrl`, la verificación ejercita la `baseUrl` derivada, que es la que usa el release.
- Cada corrida sigue publicando 2 campañas y 2 notificaciones en `dev` (AC-C01, AC-C02, AC-N01 y AC-N02).
- 2026-10-26 — Ejecutada con T-021 en `blocked`, por decisión del usuario, porque ambas van en el mismo PR. Rama `feature/7978702_queuer_acceptance_tests`, sin commit.
- Cambios: `path` y nombre del `Feature` en `campaigns_acceptance_test.feature` y `notifications_acceptance_test.feature`, conservando CRLF, y la fila `baseUrl` del README de `acceptanceTest`. Tags, `karate-config.js` y `data/` sin cambios. `grep "api/v1"` sobre las fuentes de `acceptanceTest` no da resultados (solo aparece en `build/`, que es una copia de una compilación previa).
- `docs/pruebas.md`: los encabezados pasan a `### POST /campaigns` y `### POST /notifications`, con `<a id="post-apiv1campaigns">` y `<a id="post-apiv1notifications">` antes de cada uno para no romper los enlaces de T-004 y T-005. También se actualizan la fila `baseUrl` y una mención de `/api/v1/*` en la sección E2E que T-021 no había cambiado.
- **blocked:** falta desplegar T-021 en `dev` y correr la suite (10/10 `@campaigns`, 9/9 `@notifications`, 37/37 completa).
