---
id: T-013
aliases: [T-013]
title: "trace run aguas abajo: scheduler y microservicios"
status: backlog
priority: P2
epic: E-trace
estimate: M
depends_on: [T-007, T-009]
type: task
origin: tasks/09-trace-run.md
created: 2026-10-13
---

# T-013 — `trace run` aguas abajo: scheduler y microservicios

## Objetivo
Extender `trace run` con la etapa 6 del plan original: después de la ingesta, hacer que el scheduler publique (esperando su hora o invocándolo) y buscar cada `notification_id` en los logs del scheduler, `platform_campaigns_ms` y `engine_nlp_ms`. Cierra el criterio 4 del plan hasta los microservicios.

## Archivos a crear/modificar
- `src/campaigns_cli/services/trace_service.py` — etapa 6
- `src/campaigns_cli/commands/trace_cmd.py` — opciones `--wait-schedule` e `--invoke-scheduler`
- `.env.example` — log groups de los microservicios en `CAMPAIGNS_LOG_GROUPS`
- `docs/configuracion.md` — log groups de los microservicios (hoy "sin confirmar")
- `docs/comandos.md`, `docs/recursos-aws.md`
- `tests/test_trace_service.py`, `tests/test_trace_cmd.py`

## Tareas
- [ ] Descubrir con `campaigns logs groups --prefix ...` los log groups de `platform_campaigns_ms` y `engine_nlp_ms` en dev y registrarlos en `.env.example` y en `docs/configuracion.md`.
- [ ] `--wait-schedule`: si la fecha/hora del CSV es próxima (≤ `--timeout`), esperar a que el scheduler publique.
- [ ] `--invoke-scheduler`: invocar `scheduler_Lambda` con `LambdaService` ([[T-007-lambda-invoke|T-007]]) después de la etapa 4.
- [ ] Etapa 6: buscar cada `notification_id` por componente; reportar OK/FALLA por componente.
- [ ] Sin `--wait-schedule` ni `--invoke-scheduler`, la etapa 6 no se ejecuta y no cuenta como falla.

## Criterios de aceptación
- [ ] Fakes: `notification_id` presente en todos los componentes → etapa 6 `OK`; falta en uno → `FALLA` con el componente señalado, exit 1.
- [ ] Sin las opciones nuevas, el reporte es igual al de [[T-009-trace-run|T-009]].
- [ ] `--invoke-scheduler` con `CAMPAIGNS_ENV=prod` → bloqueado.

## Verificación
```bash
uv run pytest tests/test_trace_service.py tests/test_trace_cmd.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run campaigns trace run --help | grep -E -- '--wait-schedule|--invoke-scheduler'
```

## Notas
- Fuente para `platform_campaigns_ms`: sus logs **no** llegan a CloudWatch (Container Insights sin eventos desde 2024); se leen de sus pods con `PodsService` ([[T-017-pods-logs-eks|T-017]], [ADR-0009](../../docs/adr/0009-acceso-a-kubernetes.md)); la búsqueda por `notification_id` en campaigns y engine llega con [[T-018-pods-engine-notification-id|T-018]].
- La búsqueda por `notification_id` en `platform_campaigns_ms` depende de que la HU 7938050 (`../7938050-campaigns-correlationid-trace/`) registre `correlationId` en sus logs; antes de eso puede no aparecer.
- Invocar el scheduler en dev genera envíos reales a los usuarios del CSV: requiere confirmación del usuario.
