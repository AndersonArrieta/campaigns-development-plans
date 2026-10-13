---
id: ADR-0004
title: "Sin GSI: scan filtrado por campaign_id y query por partición horaria"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0004 — Sin GSI: scan filtrado por campaign_id y query por partición horaria

## Contexto
La tabla de campañas tiene PK `datetime` (hora programada) y SK `notification_id`, y **no tiene
índices secundarios**. Crear uno es responsabilidad de IaC, fuera del alcance de la CLI.

## Decisión
- Buscar por `campaign_id`, `user` o `app_id` usa `scan` filtrado y lo avisa por stderr.
- Listar por fechas hace un `query` por cada hora del rango, con un máximo de 31 días.
- `CAMPAIGNS_TABLE_CAMPAIGN_INDEX` se mantiene: si algún día existe un GSI por `campaign_id`, `find`
  lo usa sin cambiar el código, y `config check` verifica que exista.

## Consecuencias
- `find` y `get` sin `--datetime` son lentos y costosos en tablas grandes.
- `trace run` debe preferir `list` por hora (conoce la fecha del CSV) en lugar de `find`.
- Origen: [T-006](../../backlog/tasks/T-006-dynamo-lectura.md).
