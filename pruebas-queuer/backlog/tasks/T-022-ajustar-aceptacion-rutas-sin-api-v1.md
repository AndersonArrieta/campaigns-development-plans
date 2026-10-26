---
id: T-022
aliases: [T-022]
title: "Ajustar las pruebas de aceptación a /campaigns y /notifications"
status: backlog
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
- [ ] `campaigns_acceptance_test.feature`: `path '/api/v1/campaigns'` → `path '/campaigns'` y `Feature: Acceptance Test POST /api/v1/campaigns` → `Feature: Acceptance Test POST /campaigns`.
- [ ] `notifications_acceptance_test.feature`: `path '/api/v1/notifications'` → `path '/notifications'` y el nombre del `Feature` igual.
- [ ] No tocar tags (`@acceptanceTest @campaigns`, `@acceptanceTest @notifications`), `karate-config.js` ni los JSON de `data/`.
- [ ] README de `acceptanceTest`: en la fila `baseUrl`, "rutas `/api/v1/campaigns` y `/api/v1/notifications`" → "rutas `/campaigns` y `/notifications`".
- [ ] `docs/pruebas.md`: actualizar las rutas que citan las secciones de aceptación y la tabla de propiedades. Los anclajes `#post-apiv1campaigns` y `#post-apiv1notifications` cambian si cambia el encabezado; actualizar los enlaces que los usan o conservar el encabezado con una nota.
- [ ] Confirmar que no queda `/api/v1` en el proyecto: `grep -rn "api/v1" queuer_ms/deployment/acceptanceTest` sin resultados.

## Criterios de aceptación
- [ ] Con T-021 desplegada en `dev`: `--tags @campaigns` 10/10 y `--tags @notifications` 9/9.
- [ ] Suite completa de aceptación en verde: 37/37 (17 `/queuer` + 10 campañas + 9 notificaciones + `get-token`).
- [ ] El release de aceptación no necesita variables nuevas: `baseUrl` se sigue derivando de `endpoint`.

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
