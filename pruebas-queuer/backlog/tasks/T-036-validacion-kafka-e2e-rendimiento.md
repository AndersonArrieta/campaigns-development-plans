---
id: T-036
aliases: [T-036]
title: "Validar en Kafka al cierre de la prueba E2E que cada 202 del queuer quedó publicado"
status: blocked
priority: P2
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-034]
type: task
created: 2026-11-04
---

# T-036 — Validar en Kafka al cierre de la prueba E2E que cada `202` del queuer quedó publicado

## Objetivo
Al terminar la prueba E2E, comprobar que cada `202` del queuer tiene su mensaje en el tópico, sin mezclarlo con los mensajes que publican directo `GH_campaigns` / `GH_notifications`.

Hoy `Tx_validateCampaignsNotificationsTopics` (en `GH_tearDownKafkaValidation`) cuenta por diferencia de `endOffsets` desde el inicio de la corrida y calcula el lag de los consumer groups de `platform_campaigns_ms`. Los mensajes del queuer caen en los mismos tópicos, así que ese conteo los suma a los directos.

## Documentación relacionada
- [Publicación en Kafka](../../docs/publicacion-kafka.md)
- Referencia: [[T-013-validacion-kafka-modular|T-013]] (validación por key en la prueba modular)

## Archivos a crear/modificar
- `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx`
- `Back/E2E/teams/SC_teamsJMeterTest.jmx`

## Tareas
- [x] En el teardown, si `usersCampaignsQueuer` o `usersNotificationsQueuer` > 0, contar en cada tópico los mensajes con key `qe2e-<runId>-*` (el queuer usa `metadata.Id` como key; el productor directo publica sin key) y compararlos con los contadores `qe2e.*.accepted`.
- [x] Leer sin unirse a consumer groups ni confirmar offsets (`assign()` + `offsetsForTimes` + `seek()`), como en [[T-013-validacion-kafka-modular|T-013]].
- [x] Ajustar el conteo actual para que no falle ni se distorsione cuando corren a la vez los grupos directos y los del queuer.
- [ ] Implementar y verificar primero en `SC_whatsappJMeterTest.jmx`; llevarlo a `SC_teamsJMeterTest.jmx` cuando [[T-035-e2e-rendimiento-queuer-teams|T-035]] se desbloquee.

## Criterios de aceptación
- [ ] En una corrida corta, el número de mensajes `qe2e-<runId>-*` en cada tópico es igual al número de `202` del flujo.
- [x] Con los usuarios del queuer en `0`, el teardown se comporta igual que antes del cambio.

## Verificación
```bash
# Corrida corta de T-034 con los grupos directos y los del queuer a la vez;
# revisar en el .jtl la muestra del teardown: conteo queuer == 202 por flujo y conteo directo sin cambios
```

## Notas
- Más mensajes que `202` indica duplicados por reintentos del productor; menos indica pérdida. Cualquiera de los dos se registra como bug `B-0NN`.
- `Tx_secretManager` lee el secreto `experiencia-trv` de QA; si la identidad del release no puede leerlo, la validación queda bloqueada como en [[T-013-validacion-kafka-modular|T-013]].
- 2026-11-05 — Ya no depende de [[T-035-e2e-rendimiento-queuer-teams|T-035]]: la validación por key se puede construir y verificar en WhatsApp mientras Teams sigue bloqueada por el pool de usuarios. La parte de Teams queda como tarea aparte dentro de esta tarjeta.
- 2026-11-05 — Implementado en `SC_whatsappJMeterTest.jmx` (rama `feature/8016357-queuer-e2e-performance-test` del repo PE, sin commit): +174/−4 líneas, CRLF, XML válido.
  - `Post_countAccepted*Queuer` guardan además en `props` el `runId` (`qe2e.runId`) y el inicio del primer envío (`qe2e.start.ts`, `putIfAbsent`).
  - `GH_tearDownKafkaValidation` → `If_queuerGroups` (solo si `usersCampaignsQueuer` o `usersNotificationsQueuer` > 0) → `Tx_validateQueuerTopics`, antes de `Tx_validateCampaignsNotificationsTopics`. Usa la configuración Kafka que deja `Tx_secretManager` (`V_kafka*`). Consumidor sin `group.id`: `assign()` + `offsetsForTimes(inicio − 60 s)` + `seek()` hasta los `endOffsets` (timeout 90 s). Cuenta las keys `qe2e-<runId>-*` por tópico y exige `conteo == qe2e.*.accepted`, sin keys duplicadas y lectura completa. Deja `qe2e.*.kafka.count` en `props`. Si el queuer no respondió ningún `202`, se omite con éxito.
  - `Tx_validateCampaignsNotificationsTopics` resta `qe2e.*.kafka.count` de `produced*`; con los grupos del queuer en `0` la resta es `0`.
  - Como `GH_tearDownKafkaValidation` tiene `stoptest`, si falla `Tx_validateQueuerTopics` no corre el conteo de los directos. Ese conteo sigue sin recibir `setup.status` (`Tx_preTestCampaignKafka` desactivado); no se cambió aquí (ver [[T-038-secret-manager-opcional-e2e-rendimiento|T-038]]).
- 2026-11-05 — Verificación local (JMeter 5.5 + **JRE 17** + plugins `casutg` 2.10 / `tst` 2.6, librerías de la caché de Ivy con `-Dgroovy.grape.enable=false`, Backend Listener desactivado solo en las copias, credenciales con `-q`). Con JRE 21 Groovy 3.0.11 de JMeter 5.5 no compila (`Unsupported class file major version 65`).
  - Todos los grupos en `0`: `HEAD` y la versión modificada generan las mismas muestras (`Tx_oauthToken` OK, `Tx_secretManager` falla). Sin secretos en `jmeter.log`.
  - Con la sesión AWS de `queuer-qa.env`, con y sin VPN: `FullStackQARole` → `not authorized to perform: secretsmanager:GetSecretValue on resource: nu0284001-artemis-qa-secret-operative-eda-experiencia-trv because no identity-based policy allows` (falta de permiso del rol, no de red).
  - Se empezó una prueba con Kafka local en Docker y un mock del queuer; se detuvo por decisión del usuario.
- **Bloqueada:** falta la corrida corta con los grupos directos y los del queuer a la vez y la lectura real de Kafka, porque ninguna identidad local puede leer el secreto. El usuario la hará desde el release de Azure DevOps. Cuando pase, marcar el primer criterio y la tarea de Teams queda pendiente hasta que [[T-035-e2e-rendimiento-queuer-teams|T-035]] se desbloquee.
