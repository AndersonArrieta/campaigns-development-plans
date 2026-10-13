---
id: T-011
aliases: [T-011]
title: "Validar en dev los comandos de lectura (config, dynamo, logs)"
status: todo
priority: P1
epic: E-calidad
estimate: S
depends_on: [T-003, T-006, T-008]
type: task
created: 2026-10-13
---

# T-011 — Validar en dev los comandos de lectura (`config`, `dynamo`, `logs`)

## Objetivo
Cerrar los criterios que quedaron pendientes en [[T-003-aws-output-guards|T-003]], [[T-006-dynamo-lectura|T-006]] y [[T-008-logs-cloudwatch|T-008]] porque requerían credenciales reales: comprobar contra la cuenta de dev que `config check`, `dynamo` y `logs` devuelven datos reales. Solo lectura.

## Archivos a crear/modificar
- `.env` (local, no versionado): nombres reales de dev para tablas y lambdas
- `evidencias/t011/` — salidas de los comandos (sin credenciales ni ARNs completos)

## Tareas
- [ ] Completar el `.env` con `CAMPAIGNS_TABLE_NAME`, `CAMPAIGNS_LOGS_TABLE_NAME`, `INGESTER_LAMBDA_NAME` y `SCHEDULER_LAMBDA_NAME` de dev (patrones en `.env.example`); las credenciales las pone el usuario.
- [ ] Ejecutar `config check` y revisar el estado de cada recurso.
- [ ] Tomar un `campaign_id` de una carga reciente y seguirlo en `dynamo find` y `logs search`.
- [ ] Guardar las salidas en `evidencias/t011/`.
- [ ] Si `dynamo logs` confirma o desmiente que la tabla de logs guarda UTC, anotarlo en [ADR-0006](../../docs/adr/0006-hora-colombia.md) (con un ADR nuevo si cambia la decisión) y marcar el criterio 3 en `docs/README.md`.
- [ ] Si algún comando falla contra AWS real, abrir un bug `B-0NN` con `affects:` a la tarjeta implicada (no reabrir la `done`).

## Criterios de aceptación
- [ ] `config check` muestra la identidad AWS y las dos tablas y los log groups de las lambdas en `OK`.
- [ ] `dynamo logs --since 7d` lista cargas reales y `dynamo find --campaign-id` devuelve sus notificaciones.
- [ ] `logs search --id <campaign_id>` encuentra el `campaign_id` en el log group del ingester.

## Verificación
```bash
mkdir -p evidencias/t011
uv run campaigns config check | tee evidencias/t011/config-check.txt
CID=$(uv run campaigns --output json dynamo logs --since 7d | jq -r '[.[] | select(.campaign_id)][0].campaign_id')
test -n "$CID" && test "$CID" != null
uv run campaigns dynamo find --campaign-id "$CID" | tee evidencias/t011/dynamo-find.txt
uv run campaigns logs search --id "$CID" -l ingester --since 7d | tee evidencias/t011/logs-search.txt
```

## Notas
- `config check` sale con 1 mientras falten el bucket o algún recurso; para esta tarjeta basta con que tablas y log groups salgan `OK`.
- Las credenciales temporales (`ASIA...`) vencen en pocas horas: si sale "Sin credenciales" o "vencidas", pedir al usuario que las renueve.
- Si `dynamo logs` no muestra cargas recientes, ampliar `--since` (la tabla de logs guarda la fecha en UTC).
