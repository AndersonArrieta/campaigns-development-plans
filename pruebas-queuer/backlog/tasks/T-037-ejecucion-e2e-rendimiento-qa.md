---
id: T-037
aliases: [T-037]
title: "Ejecutar las pruebas E2E de rendimiento por el queuer en QA, línea base y evidencias"
status: backlog
priority: P2
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-034, T-035, T-036]
type: task
created: 2026-11-04
---

# T-037 — Ejecutar las pruebas E2E de rendimiento por el queuer en QA, línea base y evidencias

## Objetivo
Ejecutar desde el release los grupos E2E por el queuer en WhatsApp y Teams con el perfil de carga acordado, dejar la línea base (tiempos de respuesta, throughput y errores) y compararla con la entrada directa a Kafka.

## Documentación relacionada
- [Guía de pruebas](../../docs/pruebas.md)
- [Latencia atada a los reintentos de Kafka](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)

## Archivos a crear/modificar
- Variables del release de las pruebas E2E de rendimiento (las configura el usuario)
- `docs/pruebas.md` (sección de pruebas E2E de rendimiento)

## Tareas
- [ ] Configurar en el release las propiedades nuevas de [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]] (secretos como variables secretas).
- [ ] Definir el perfil de carga (TPS, rampa, duración) y el umbral de tiempo de respuesta con los límites de [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]].
- [ ] Ejecutar WhatsApp y Teams con los grupos directos y los del queuer en la misma corrida.
- [ ] Registrar en `docs/pruebas.md` la línea base por transacción (p50, p95, p99, TPS, % de error), el resultado de [[T-036-validacion-kafka-e2e-rendimiento|T-036]] y la comparación queuer vs. directo.

## Criterios de aceptación
- [ ] La ejecución desde el release termina con las métricas en Elasticsearch (`Tx_campaignsQueuerTest`, `Tx_notificationsQueuerTest`) y la validación en Kafka sin diferencias.
- [ ] La línea base y las evidencias quedan en `docs/pruebas.md`.

## Verificación
```bash
# Release de las pruebas E2E de rendimiento en QA; revisar el dashboard de Elasticsearch por ID_PRUEBA
# y el resultado del teardown en el log del release
```

## Notas
- Un desvío de latencia o de errores atribuible al servicio se registra como bug `B-0NN` sobre `queuer_ms`, no se corrige en el script.
