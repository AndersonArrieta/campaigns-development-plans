---
id: T-018
aliases: [T-018]
title: "pods: componente engine y búsqueda por notification_id en campaigns y engine"
status: done
priority: P2
epic: E-logs
estimate: M
depends_on: [T-017]
type: task
affects: [T-017]
created: 2026-10-13
---

# T-018 — `pods`: componente engine y búsqueda por `notification_id` en campaigns y engine

## Objetivo
Después de revisar `platform_campaigns_ms` (`app=platform-campaigns-others-v2`) hay que revisar también
`engine_nlp_ms` (`app=platform-engine-nlp-others-campaigns`). Hoy se puede con
`-l app=platform-engine-nlp-others-campaigns`, pero hay que recordar el selector y consultar cada
componente por separado. Esta tarjeta:

1. Da nombre a los componentes (`campaigns`, `engine`) para elegirlos sin escribir el selector.
2. Agrega `--notification-id`, que busca ese id en los logs de **los dos** componentes a la vez y
   resume en cuál aparece. Es el rastro de una notificación desde `platform_campaigns_ms` hasta el engine.

Amplía el grupo `pods` de [[T-017-pods-logs-eks|T-017]].

Verificado en dev (2026-10-13): `pods ls -l app=platform-engine-nlp-others-campaigns` devuelve un pod
(`platform-engine-nlp-others-campaigns-…`, contenedores `platform-engine-nlp-others-campaigns` e
`istio-proxy`). En sus logs, el `notification_id` aparece dentro del body JSON del mensaje recibido
(`"notification_id":"213bc663-…"`), y las líneas relacionadas (`Message null Headers`,
`Sending message to Retry DLQ`) van justo antes y después, sin el id.

## Archivos a crear/modificar
- `src/campaigns_cli/settings.py` — `ENGINE_POD_SELECTOR` (por defecto `app=platform-engine-nlp-others-campaigns`)
- `src/campaigns_cli/services/k8s_service.py` — `Component` (`campaigns`, `engine`) con su selector; `PodLogLine.component`; `search(notification_id, components, since, context)` con resumen por componente
- `src/campaigns_cli/commands/pods_cmd.py` — opciones `--component`, `--notification-id`, `--context`
- `src/campaigns_cli/services/config_service.py` — la fila "EKS" cuenta los pods de cada componente
- `.env.example`
- `tests/k8s_fixtures.py`, `tests/test_k8s_service.py`, `tests/test_pods_cmd.py`, `tests/test_config_check.py`, `tests/test_settings.py`
- `docs/comandos.md`, `docs/configuracion.md`, `docs/recursos-aws.md`, `docs/README.md`, `README.md`

## Tareas
- [x] `Component`: `campaigns` → `CAMPAIGNS_POD_SELECTOR`, `engine` → `ENGINE_POD_SELECTOR`.
- [x] `--component campaigns|engine|all` (`-k`, repetible) en `pods ls` y `pods logs`; por defecto `campaigns` (como hoy). `-l SELECTOR` sigue funcionando y tiene prioridad.
- [x] `pods ls --component all`: una tabla con la columna `componente`.
- [x] Cada línea de log lleva su componente: en texto, `[campaigns]`/`[engine]` antes del pod; en JSON, campo `componente`.
- [x] `pods logs --notification-id ID`:
  - Por defecto busca en **todos** los componentes (`--component` lo acota) y en las últimas 24 h (`--since` lo cambia); `--tail` no aplica salvo que se pase.
  - Equivale a `--filter ID` sobre el texto literal (encuentra el id también dentro de JSON) y valida que tenga al menos 6 caracteres, como `logs search`.
  - Al final, un resumen por componente: líneas encontradas y hora de la primera y la última (stderr en texto; `resumen` en JSON).
  - Sale con 1 si el id no aparece en ningún componente (como `logs search`).
- [x] `--context N` (con `--filter` o `--notification-id`): muestra también las N líneas anteriores y posteriores de **ese mismo pod**, como `grep -C`, marcando la coincidencia. Así se ven las líneas relacionadas que no llevan el id (p. ej. `Sending message to Retry DLQ`).
- [x] `-f` con varios componentes: `--max-pods` cuenta los pods de todos; con `--notification-id` y `-f`, solo muestra las líneas nuevas que lo contengan.
- [x] `config check`: la fila "EKS" informa `N pod(s) campaigns, M pod(s) engine`; un componente sin pods no es error (puede estar escalado a 0), pero se indica en el detalle.
- [x] Documentar en `docs/comandos.md` (componentes, `--notification-id`, `--context`), `docs/configuracion.md` (`ENGINE_POD_SELECTOR`), `docs/recursos-aws.md` (pods del engine en dev) y `README.md`.

## Criterios de aceptación
- [x] `pods logs --component engine` consulta solo los pods con `app=platform-engine-nlp-others-campaigns`.
- [x] `pods logs --notification-id <id>` consulta los pods de campaigns y engine con `sinceSeconds=86400`, deja solo las líneas que contienen el id y muestra el resumen por componente.
- [x] Si el id aparece solo en campaigns, el resumen marca engine con 0 coincidencias y el comando sale con 0; si no aparece en ninguno, sale con 1.
- [x] `--context 2` muestra, por pod, las 2 líneas anteriores y posteriores a cada coincidencia sin repetir líneas cuando los contextos se solapan.
- [x] `--notification-id abc` (menos de 6 caracteres) → error de uso (exit 2).
- [x] Sin `--component` ni `--notification-id`, `pods ls` y `pods logs` se comportan igual que en T-017.

## Verificación
```bash
uv run pytest tests/test_k8s_service.py tests/test_pods_cmd.py tests/test_config_check.py tests/test_settings.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run campaigns pods logs --help | grep -E -- '--component|--notification-id|--context'
# en dev (solo lectura; requiere EKS_* en el .env)
uv run campaigns pods ls --component all
NID=$(uv run campaigns --output json dynamo list --date "$(date +%F)" -n 1 | jq -r '.[0].notification_id')
uv run campaigns pods logs --notification-id "$NID" --context 2
```

## Notas
- `affects: [T-017]` porque amplía el grupo `pods` y `k8s_service.py` de esa tarjeta.
- Si el comando de dev falla, se registra como bug con `affects: [T-018]`.
- Que el `notification_id` aparezca en los logs de `platform_campaigns_ms` depende de la HU 7938050 (registrar `correlationId`); en el engine ya aparece dentro del body del mensaje.
- En la muestra de dev, el engine registró `Message null … Sending message to Retry DLQ` para una notificación de `others-test`. No es parte de esta tarjeta, pero `--notification-id … --context` sirve justamente para investigarlo (relacionado con la task 16 de la HU 7938050, feedback de reintento del engine).
- Servirá en [[T-013-trace-aguas-abajo|T-013]] para buscar cada `notification_id` en campaigns y engine.
- **Cerrada (2026-10-13):** 264 pruebas en verde (96 % de cobertura), ruff y mypy sin errores. Las pruebas de T-017 que comparaban la salida exacta se ajustaron: las líneas llevan ahora `[componente]`, el JSON el campo `componente` y el mensaje sin pods dice "No hay pods de campaigns…" (mismos códigos de salida).
- **Dev:** `pods ls --component all` lista un pod de cada componente. El `notification_id` del comando de verificación (`f1be0f5c-…`, programado a las 10:00) no aparece en ningún componente, porque el pod de campaigns se reinició (`…-r5lmf`) y el engine no guarda logs de esa hora; el comando sale con 1, como se espera. Con `213bc663-cad7-48bb-a39f-a1719b547303` (16:00) encuentra 2 coincidencias en el engine y `-C 2` muestra la causa: `IllegalArgumentException: Invalid URL feedback` con `feedback_url=http://platform-campaigns-others-v2-service:8080/v1/retry`, seguida de `Sending message to Retry DLQ`.
