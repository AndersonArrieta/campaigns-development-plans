---
id: T-036
aliases: [T-036]
title: "Validar en Kafka al cierre de la prueba E2E que cada 202 del queuer quedó publicado"
status: backlog
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
- [ ] En el teardown, si `usersCampaignsQueuer` o `usersNotificationsQueuer` > 0, contar en cada tópico los mensajes con key `qe2e-<runId>-*` (el queuer usa `metadata.Id` como key; el productor directo publica sin key) y compararlos con los contadores `qe2e.*.accepted`.
- [ ] Leer sin unirse a consumer groups ni confirmar offsets (`assign()` + `offsetsForTimes` + `seek()`), como en [[T-013-validacion-kafka-modular|T-013]].
- [ ] Ajustar el conteo actual para que no falle ni se distorsione cuando corren a la vez los grupos directos y los del queuer.
- [ ] Implementar y verificar primero en `SC_whatsappJMeterTest.jmx`; llevarlo a `SC_teamsJMeterTest.jmx` cuando [[T-035-e2e-rendimiento-queuer-teams|T-035]] se desbloquee.

## Criterios de aceptación
- [ ] En una corrida corta, el número de mensajes `qe2e-<runId>-*` en cada tópico es igual al número de `202` del flujo.
- [ ] Con los usuarios del queuer en `0`, el teardown se comporta igual que antes del cambio.

## Verificación
```bash
# Corrida corta de T-034 con los grupos directos y los del queuer a la vez;
# revisar en el .jtl la muestra del teardown: conteo queuer == 202 por flujo y conteo directo sin cambios
```

## Notas
- Más mensajes que `202` indica duplicados por reintentos del productor; menos indica pérdida. Cualquiera de los dos se registra como bug `B-0NN`.
- `Tx_secretManager` lee el secreto `experiencia-trv` de QA; si la identidad del release no puede leerlo, la validación queda bloqueada como en [[T-013-validacion-kafka-modular|T-013]].
- 2026-11-05 — Ya no depende de [[T-035-e2e-rendimiento-queuer-teams|T-035]]: la validación por key se puede construir y verificar en WhatsApp mientras Teams sigue bloqueada por el pool de usuarios. La parte de Teams queda como tarea aparte dentro de esta tarjeta.
