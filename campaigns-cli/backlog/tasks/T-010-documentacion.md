---
id: T-010
aliases: [T-010]
title: "Documentación de uso completa y cierre de criterios del plan"
status: backlog
priority: P2
epic: E-calidad
estimate: S
depends_on: [T-007, T-009]
type: task
origin: tasks/10-documentacion-ci.md
created: 2026-10-13
---

# T-010 — Documentación de uso completa y cierre de criterios del plan

## Objetivo
Dejar el `README.md` listo para que otra persona del equipo instale y use la CLI sin ayuda, con todos los grupos de comandos, y cerrar los criterios de aceptación de [`docs/README.md`](../../docs/README.md#criterios-de-aceptación-del-proyecto). El pipeline de CI va aparte en [[T-014-ci-github-actions|T-014]].

## Archivos a crear/modificar
- `README.md`
- `.env.example`
- `docs/README.md` — estado por grupo y criterios de aceptación

## Tareas
- [ ] `README.md`: requisitos, WSL + OneDrive (`UV_PROJECT_ENVIRONMENT`), instalación (`uv sync`, opcional `uv tool install --editable .`), configuración (`.env`, `--env-file .env.qa`), un ejemplo por grupo (`config`, `csv`, `s3`, `lambda`, `dynamo`, `logs`, `trace`).
- [ ] Receta típica: `csv generate` → `trace run` → `logs search` → `dynamo purge`.
- [ ] Protecciones (qué se bloquea en prod, `--yes`), códigos de salida y autocompletado (`campaigns --install-completion`).
- [ ] Desarrollo: cómo agregar un grupo (`commands/` + `services/` + registro en `main.py`).
- [ ] `.env.example` con los patrones de nombres reales de dev (sin secretos).
- [ ] Marcar en `docs/README.md` los criterios de aceptación cumplidos y dejar la tabla de estado por grupo al día.
- [ ] Revisar que `docs/comandos.md` y `docs/configuracion.md` coinciden con `campaigns <grupo> --help` y `.env.example`.

## Criterios de aceptación
- [ ] Cada grupo registrado en `main.py` tiene al menos un ejemplo en el README.
- [ ] Una instalación desde un entorno virtual vacío funciona siguiendo el README.
- [ ] `.env.example` no contiene valores de credenciales.

## Verificación
```bash
for g in config csv s3 lambda dynamo logs trace; do uv run campaigns $g --help >/dev/null && grep -q "campaigns $g" README.md && echo "OK $g" || echo "FALTA $g"; done
UV_PROJECT_ENVIRONMENT="$(mktemp -d)/venv" uv sync --locked
UV_PROJECT_ENVIRONMENT="$(mktemp -d)/venv" uv run campaigns --help
grep -E '^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY|SESSION_TOKEN)=.+' .env.example && echo "HAY SECRETOS" || echo "sin secretos"
```

## Notas
- "README probado por alguien distinto a quien desarrolló la CLI" (plan original) lo hace una persona; no es criterio de cierre del agente.
