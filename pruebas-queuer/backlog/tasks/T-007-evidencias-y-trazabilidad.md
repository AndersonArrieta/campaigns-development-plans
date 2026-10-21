---
id: T-007
aliases: [T-007]
title: "Ejecutar suites en dev, archivar evidencias y actualizar trazabilidad en docs"
status: backlog
priority: P2
epic: E-trazabilidad
estimate: S
depends_on: [T-004, T-005, T-006]
type: task
created: 2026-10-21
---

# T-007 — Ejecutar suites en `dev`, archivar evidencias y actualizar trazabilidad

## Objetivo
Correr las suites completas de aceptación y humo en `dev` con los escenarios nuevos, guardar los reportes como evidencia y dejar en `docs/pruebas.md` la trazabilidad final entre casos documentados, escenarios Karate y tarjetas.

## Documentación relacionada
- [Guía de pruebas — Automatización en Karate](../../docs/pruebas.md#automatización-en-karate)
- [Observaciones](../../docs/observaciones.md)

## Archivos a crear/modificar
- `pruebas-queuer/evidencias/$(date +%F)-acceptance/` y `$(date +%F)-smoke/` (reportes `cucumber-html-reports` y `karate-reports` copiados de `target/`)
- `pruebas-queuer/docs/pruebas.md`

## Tareas
- [ ] Ejecutar la suite completa de aceptación y la de humo en `dev`.
- [ ] Copiar los reportes a `pruebas-queuer/evidencias/$(date +%F)-acceptance/` y `$(date +%F)-smoke/`, revisando que no contengan el token ni el `clientSecret`.
- [ ] En `docs/pruebas.md`, cambiar el estado de cada escenario de la tabla de automatización de "Planeado" a "Automatizado" y enlazar la evidencia.
- [ ] Proponer al usuario un bug `B-0NN` por cada defecto de las [observaciones 1–4](../../docs/observaciones.md) que se confirme en la ejecución (incluye los casos sin automatizar C-13, C-14 y N-06), con `epic` de la capacidad afectada.

## Criterios de aceptación
- [ ] Ambas suites en verde en `dev`, con fecha y versión de imagen anotadas en las notas de esta tarjeta.
- [ ] Evidencias archivadas sin secretos.
- [ ] `docs/pruebas.md` refleja el estado real de la automatización.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment
(cd acceptanceTest && ./gradlew clean test -Dendpoint="$URL_EXT/queuer" -DbaseUrl="$URL_EXT" -DkafkaAppId="$KAFKA_APP_ID" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET")
(cd smokeTest && ./gradlew clean test -Dendpoint="$URL_EXT/actuator/health" -DbaseUrl="$URL_EXT" \
  -DcognitoEndpoint="$COGNITO_URL" -DclientId="$CLIENT_ID" -DclientSecret="$CLIENT_SECRET")

EV="/mnt/c/Users/AndersonElitArrietaR/OneDrive - FINAIPRO TECHNOLOGIES SAS/Documentos/campaigns-development-plans/pruebas-queuer/evidencias"
# Ninguna evidencia debe contener secretos
! grep -rl -e "$CLIENT_SECRET" -e "Bearer ey" "$EV"
# Ningun escenario queda como "Planeado"
! grep -n "Planeado" "$EV/../docs/pruebas.md"
```

## Notas
-
