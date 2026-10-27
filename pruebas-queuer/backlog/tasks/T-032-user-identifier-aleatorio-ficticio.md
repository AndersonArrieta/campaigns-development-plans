---
id: T-032
aliases: [T-032]
title: "userIdentifier aleatorio dentro de un rango ficticio en las pruebas de aceptación de /campaigns y /notifications"
status: blocked
priority: P2
epic: E-aceptacion
estimate: S
depends_on: []
affects: [T-004, T-005, T-026]
type: task
created: 2026-10-27
---

# T-032 — `userIdentifier` aleatorio dentro de un rango ficticio en las pruebas de aceptación de `/campaigns` y `/notifications`

## Objetivo
Hoy `campaigns_acceptance_test.feature` y `notifications_acceptance_test.feature` fijan en el `Background` `body.data.userIdentifier = '573000000000'`, el número ficticio aprobado en [[T-003-datos-prueba-kafka-dev|T-003]]. El usuario pidió que sea aleatorio en cada escenario (opción 2 de la revisión del 2026-10-27): un valor que cambie en cada ejecución pero que se mantenga en un **rango ficticio**, `57300000` + 4 dígitos aleatorios (`573000000000`–`573000009999`), para no apuntar a un celular real si `platform_campaigns_ms` entrega los mensajes por un canal real en `dev`.

## Documentación relacionada
- [Datos de prueba en dev](../../docs/pruebas.md#datos-de-prueba-en-dev)
- [[T-004-aceptacion-campaigns|T-004]], [[T-005-aceptacion-notifications|T-005]], [[T-026-validar-mensaje-kafka-aceptacion|T-026]]

## Archivos a crear/modificar
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/campaigns_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/src/test/resources/co/com/bancolombia/notifications_acceptance_test.feature`
- `queuer_ms/deployment/acceptanceTest/README.md` (si menciona el `userIdentifier` fijo)
- `pruebas-queuer/docs/pruebas.md` (tabla "Datos de prueba en dev": `userIdentifier` ficticio)

## Tareas
- [x] En el `Background` de ambos features, reemplazar `* set body.data.userIdentifier = '573000000000'` por un valor aleatorio en el rango ficticio, por ejemplo `* def userIdentifier = '57300000' + ('000' + Math.floor(Math.random() * 10000)).slice(-4)` y `* set body.data.userIdentifier = userIdentifier`. Siempre 12 dígitos.
- [x] El valor se genera por escenario (el `Background` corre en cada uno). Los escenarios `202` lo validan en Kafka a través de `data contains deep`, así que no requieren cambios en el helper.
- [x] No tocar el escenario que quita `data.userIdentifier` (AC-N07): sigue esperando el `400`.
- [x] Código en inglés y sin comentarios (preferencia del usuario).
- [x] Actualizar `docs/pruebas.md` y, si aplica, el README: `userIdentifier` = `57300000` + 4 dígitos aleatorios (rango ficticio).
- [ ] Confirmar con el equipo dueño del canal en `dev` que el prefijo `57300000` no corresponde a líneas asignadas, o dejarlo anotado como pendiente si no se puede confirmar.

## Criterios de aceptación
- [x] Cada escenario usa un `userIdentifier` de 12 dígitos que empieza por `57300000`.
- [ ] Los escenarios `202` siguen encontrando y validando su mensaje en Kafka con ese `userIdentifier`.
- [ ] La suite completa pasa en `dev`: 36/36.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_MR/queuer_ms/deployment/acceptanceTest
grep -n "userIdentifier" src/test/resources/co/com/bancolombia/*_acceptance_test.feature
# Local: comprobar la expresion en un feature temporal (Karate 1.0.1): 100 valores, todos 12 digitos y prefijo 57300000
# dev (release o local con VPN y credenciales): suite 36/36; en el log, los userIdentifier de los mensajes publicados cumplen el rango
```

## Notas
- La búsqueda en Kafka es por `metadata.Id`, no por `userIdentifier`, así que la aleatoriedad no afecta la validación en Kafka.
- Por la preferencia registrada en memoria, se valida en `dev`; en local solo se comprueba la expresión.
- 2026-10-27 — Ejecutado en `feature/7978702_queuer_acceptance_tests`. Sin commit.
- `campaigns_acceptance_test.feature` y `notifications_acceptance_test.feature`: en el `Background`, `* def userIdentifier = '57300000' + ('000' + Math.floor(Math.random() * 10000)).slice(-4)` y `* set body.data.userIdentifier = userIdentifier`. Sin comentarios y con CRLF. AC-N07 (`remove body.data.userIdentifier`) sin cambios. El README no mencionaba el valor fijo; `docs/pruebas.md` actualizado.
- Verificación local con Karate 1.0.1 (feature temporal en el scratchpad): 1000 valores generados con la misma expresión, todos `string`, 12 dígitos y prefijo `57300000`.
- **blocked:** falta (1) la suite en `dev` (36/36, con los escenarios `202` validando el `userIdentifier` en Kafka) y (2) que el usuario confirme con el equipo dueño del canal en `dev` que el prefijo `57300000` no corresponde a líneas asignadas.
