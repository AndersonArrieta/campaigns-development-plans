---
id: ADR-0006
title: "Hora Colombia en la entrada y salida de la CLI"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0006 — Hora Colombia en la entrada y salida de la CLI

## Contexto
El ingester y el scheduler programan en hora Colombia (UTC-5) y así guardan la PK `datetime` de la
tabla de campañas. CloudWatch trabaja en epoch y Logs Insights devuelve UTC. La tabla de logs
guarda `datetime.now()` de la Lambda (UTC).

## Decisión
- Las fechas que se escriben y se muestran en `dynamo get/find/list` y en `logs` son **hora
  Colombia** sin zona; la conversión vive en `timeutils.py`.
- Excepción: `dynamo logs` usa **UTC**, porque compara contra el texto guardado por la Lambda.

## Consecuencias
- Si una carga reciente no aparece con `dynamo logs --since 2h`, hay que ampliar la ventana:
  la suposición de UTC aún no se ha comprobado en dev ([T-011](../../backlog/tasks/T-011-validar-lectura-dev.md)).
- Origen: [T-006](../../backlog/tasks/T-006-dynamo-lectura.md), [T-008](../../backlog/tasks/T-008-logs-cloudwatch.md).
