---
id: T-016
aliases: [T-016]
title: "trace run: etapa de entrega en el fake channel"
status: backlog
priority: P2
epic: E-entrega
estimate: M
depends_on: [T-013, T-015]
type: task
created: 2026-10-13
---

# T-016 — `trace run`: etapa de entrega en el fake channel

## Objetivo
Cerrar `trace run` igual que la prueba E2E de `Platform_test` (`campaigns.feature`): después de que
el scheduler publique ([[T-013-trace-aguas-abajo|T-013]], con `--invoke-scheduler` o
`--wait-schedule`), verificar con `FakeChannel.wait_for` ([[T-015-fake-channel-messages|T-015]]) que
cada usuario del CSV recibió el mensaje esperado.

## Archivos a crear/modificar
- `src/campaigns_cli/services/trace_service.py` — etapa "Entrega en canal"
- `src/campaigns_cli/commands/trace_cmd.py` — opciones `--verify-delivery`, `--expected-text`, `--verify-user`
- `.env.example`, `src/campaigns_cli/settings.py` — `CLI_EXPECTED_TEXT` (por defecto vacío)
- `tests/test_trace_service.py`, `tests/test_trace_cmd.py`
- `docs/comandos.md`, `docs/README.md` (criterio 4)

## Tareas
- [ ] `--verify-delivery` (requiere `--invoke-scheduler` o `--wait-schedule`): por cada usuario del CSV, `wait_for(canal, usuario, texto)` con `--attempts` y `--interval` (por defecto 5 × 10 s, como `Platform_test`).
- [ ] Canal desde la columna `canal` del CSV: `WhatsApp` → `whatsapp`; `msteams` → `teams`.
- [ ] `--verify-user USUARIO=ID` (repetible): en Teams el CSV lleva el email del usuario pero el fake channel se consulta por `recipient.id` (UUID); sin mapeo para un usuario de Teams → etapa `FALLA` con un mensaje que lo pida.
- [ ] Texto esperado: `--expected-text`, o `CLI_EXPECTED_TEXT`; sin ninguno → error de uso. (En `Platform_test` es `Campaig_e2e_test_delivered_successfully` con el nodo `N-03-99-10`.)
- [ ] Reporte por usuario (`OK` / `FALLA` con el último motivo) dentro del `TraceReport`.

## Criterios de aceptación
- [ ] Fakes: todos los usuarios reciben el texto → etapa `OK`; uno no → `FALLA` señalando el usuario, exit 1.
- [ ] Sin `--verify-delivery`, el reporte es igual al de [[T-013-trace-aguas-abajo|T-013]].
- [ ] Usuario de Teams sin `--verify-user` → `FALLA` con mensaje claro, sin llamar al fake channel.
- [ ] En dev, `trace run` de un CSV de WhatsApp con nodo `N-03-99-10`, `--invoke-scheduler` y `--verify-delivery` termina con todas las etapas en `OK` (evidencia en `evidencias/t016/`).

## Verificación
```bash
uv run pytest tests/test_trace_service.py tests/test_trace_cmd.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run campaigns trace run --help | grep -E -- '--verify-delivery|--expected-text|--verify-user'
# en dev (requiere confirmación del usuario: dispara la ingesta y un envío real al fake channel)
mkdir -p evidencias/t016
uv run campaigns csv generate --users 574141179337 --canal WhatsApp --fecha hoy --hora +0 --nodo N-03-99-10 -o evidencias/t016/campaign.csv
uv run campaigns --yes trace run evidencias/t016/campaign.csv --invoke-scheduler --verify-delivery --expected-text Campaig_e2e_test_delivered_successfully 2>&1 | tee evidencias/t016/trace-run.txt
```

## Notas
- El fake channel no tiene endpoint de borrado: si un usuario ya tenía el mismo texto de una corrida anterior, la etapa puede dar un falso OK. Si la respuesta no trae fecha, conviene usar un texto o usuario distinto por corrida; revisarlo al implementar.
