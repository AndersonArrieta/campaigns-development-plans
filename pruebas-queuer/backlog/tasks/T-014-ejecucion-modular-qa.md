---
id: T-014
aliases: [T-014]
title: "Ejecutar las pruebas modulares en QA, línea base y evidencias"
status: backlog
priority: P2
epic: E-modular
estimate: M
depends_on: [T-011, T-012, T-013]
type: task
created: 2026-10-22
---

# T-014 — Ejecutar las pruebas modulares en QA, línea base y evidencias

## Objetivo
Correr la prueba modular de los endpoints Kafka en QA con un perfil de carga acordado, obtener una línea base de rendimiento, dejar evidencias trazables y documentarlo en `docs/pruebas.md`. Las observaciones de rendimiento que se confirmen pasan a bugs.

## Documentación relacionada
- [Guía de pruebas — modulares](../../docs/pruebas.md#pruebas-modulares-jmeter)
- Observaciones [5 (latencia)](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka), [6 (`.block()`)](../../docs/observaciones.md#6-kafkasecretproviderloadsecret-usa-block), [8 (health global)](../../docs/observaciones.md#8-health-global-y-sensible-a-errores-de-negocio) y [9 (DynamoDB por request)](../../docs/observaciones.md#9-configuración-leída-de-dynamodb-en-cada-request)

## Archivos a crear/modificar
- `docs/pruebas.md`, sección de pruebas modulares: perfil, resultados y estado.
- Evidencias (resumen de `.jtl`, capturas de Kibana) fuera del vault o en una carpeta `evidencias/` sin datos sensibles.

## Tareas
- [ ] Acordar con el usuario o el equipo el perfil de carga (TPS objetivo por endpoint, duración, usuarios) y los umbrales de aceptación (p95, % de error). **No hay valores definidos todavía.**
- [ ] Corrida 1, calentamiento: 1 TPS por endpoint durante 60 s, con `validateKafka=true`. Debe incluir el primer request con el pod recién levantado para observar la observación 6.
- [ ] Corrida 2, objetivo: TPS acordados, los dos endpoints en simultáneo, con `validateKafka=true`.
- [ ] Durante las corridas, revisar `/actuator/health` del queuer, el CPU y la memoria de los pods, el HPA y las métricas de lectura de DynamoDB.
- [ ] Registrar por transacción: TPS logrado, p50, p95, p99, % de error y resultado de la validación Kafka. Usar `ID_PRUEBA` (`idPrueba`) para filtrar en Kibana.
- [ ] Actualizar en `docs/pruebas.md` la tabla de pruebas modulares (estado `Ejecutado`, fecha, versión de imagen).
- [ ] Proponer un bug `B-0NN` por cada observación confirmada con evidencia (latencia > umbral, `.block()`, health `DOWN`, conteo Kafka distinto).

## Criterios de aceptación
- [ ] Hay al menos una corrida objetivo completa con resultados documentados y la validación Kafka en verde, o el fallo registrado como bug.
- [ ] La línea base queda en `docs/pruebas.md` con fecha y versión desplegada.
- [ ] La corrida actual de `GH_queuer` (VariableSetter) sigue funcionando sin cambios en las variables del release.

## Verificación
```bash
cd "/mnt/c/Users/AndersonElitArrietaR/OneDrive - FINAIPRO TECHNOLOGIES SAS/Documentos/campaigns-development-plans/pruebas-queuer"
grep -nE 'MOD-C0|MOD-N0|MOD-K0' docs/pruebas.md | grep -v Planeado   # todas las filas deben tener estado distinto de Planeado
grep -rnE 'clientSecret=|password|awsSecretKey=' docs backlog | grep -v 'xxx' || echo "sin secretos"
```

## Notas
- Las corridas en QA con TPS por encima del calentamiento son una acción con efecto real en el ambiente y aguas abajo (`platform_campaigns_ms`). Requieren confirmación explícita del usuario.
