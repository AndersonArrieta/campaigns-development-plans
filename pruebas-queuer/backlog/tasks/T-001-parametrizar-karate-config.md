---
id: T-001
aliases: [T-001]
title: "Parametrizar URL base y timeout de Kafka en los karate-config.js"
status: todo
priority: P1
epic: E-entorno
estimate: S
depends_on: []
type: task
created: 2026-10-21
---

# T-001 — Parametrizar URL base y timeout de Kafka en los `karate-config.js`

## Objetivo
Hoy los dos proyectos Karate reciben una sola URL completa por `-Dendpoint`: en `acceptanceTest` apunta a `/queuer` y en `smokeTest` al health. Los escenarios nuevos necesitan llamar a `/api/v1/campaigns` y `/api/v1/notifications`, así que hace falta una **URL base** del servicio. Además, `readTimeout` está fijado en 2000 ms y los endpoints Kafka responden después del ack del broker (primer request: lectura del secreto + creación del productor), por lo que necesitan un timeout propio.

El cambio debe ser **retrocompatible**: el release actual solo pasa `endpoint`, `cognitoEndpoint`, `clientId` y `clientSecret`, y los escenarios existentes deben seguir funcionando sin tocar sus variables.

## Documentación relacionada
- [Respuestas síncronas al ack de Kafka y reintentos](../../docs/publicacion-kafka.md#4-resiliencia)
- [Observación 5: latencia atada a los reintentos](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/resources/karate-config.js`
- `queuer_ms/deployment/smokeTest/src/test/resources/karate-config.js`
- `queuer_ms/deployment/acceptanceTest/README.md`
- `queuer_ms/deployment/smokeTest/README.md`

## Tareas
- [ ] En ambos `karate-config.js`, exponer `baseUrl`: valor de `karate.properties['baseUrl']`; si no viene, derivarlo de `endpoint` quitando el sufijo conocido (`/queuer` en aceptación, `/actuator/health` en humo).
- [ ] Exponer `kafkaReadTimeout`: `karate.properties['kafkaReadTimeout']` o `30000` por defecto. No cambiar el `readTimeout` global de 2000 ms (lo usan los escenarios de `/queuer` y health).
- [ ] Exponer `kafkaAppId` (`karate.properties['kafkaAppId']`, sin valor por defecto productivo; el valor de `dev` se define en [[T-003-datos-prueba-kafka-dev|T-003]]).
- [ ] Registrar con `karate.log` la `baseUrl` efectiva (sin secretos).
- [ ] Documentar las propiedades nuevas en una sección "Propiedades" de cada `README.md` de `deployment/`.

## Criterios de aceptación
- [ ] Con solo `-Dendpoint="$URL_EXT/queuer"`, `baseUrl` resulta `$URL_EXT` (y con `-Dendpoint="$URL_EXT/actuator/health"` en humo, también `$URL_EXT`).
- [ ] Con `-DbaseUrl=...` explícito, ese valor tiene prioridad.
- [ ] Los escenarios existentes de `acceptance_test.feature` y `smoke_test.feature` pasan sin cambios en sus parámetros.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
# Suite existente sin propiedades nuevas: debe seguir en verde y loguear la baseUrl derivada
./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DcognitoEndpoint="$COGNITO_URL" \
  -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i | grep -E "baseUrl|Tests|FAIL"

cd ../smokeTest
./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" -DcognitoEndpoint="$COGNITO_URL" \
  -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET" -i | grep -E "baseUrl|Tests|FAIL"
# URL_EXT, COGNITO_URL, CLIENT_ID, CLIENT_SECRET: tomar de queuer-cognito-recipe-test/config.env (URL_EXT = SCHEME://GW_EXT + PREFIX_EXT)
```

## Notas
- Supuesto a confirmar: el `-Dendpoint` del release de humo termina en `/actuator/health`. Si no, pedir que el release pase `-DbaseUrl`.
