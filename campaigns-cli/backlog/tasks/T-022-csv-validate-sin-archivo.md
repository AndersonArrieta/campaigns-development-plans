---
id: T-022
aliases: [T-022]
title: "csv validate sin argumento: validar el único CSV de data/"
status: done
priority: P2
epic: E-csv
estimate: S
depends_on: [T-004, T-021]
type: task
affects: [T-004]
created: 2026-10-16
---

# T-022 — `csv validate` sin argumento: validar el único CSV de `data/`

## Objetivo
Igual que [[T-021-s3-upload-sin-archivo|T-021]] para `s3 upload`: `uv run campaigns csv validate`
sin argumento valida el CSV de `data/`, para no tener que escribir el nombre del archivo en cada
prueba. Amplía [[T-004-csv-generate-validate|T-004]].

## Archivos a crear/modificar
- `src/campaigns_cli/commands/csv_cmd.py` — `archivo` opcional en `validate` (reutiliza `find_single_csv`)
- `tests/test_csv_cmd.py`
- `docs/comandos.md`, `README.md`

## Tareas
- [x] `csv validate [archivo]`: sin `archivo`, usa `find_single_csv()` y muestra cuál (`Archivo: data/<nombre>.csv`).
  - Varios → `UsageError` (exit 2) con la lista; mismo criterio que `s3 upload`.
  - Ninguno o sin carpeta `data/` → `UsageError` (exit 2) con la indicación de la plantilla.
- [x] Con `archivo`, el comportamiento de T-004 no cambia.
- [x] Actualizar `docs/comandos.md` y `README.md`.

## Criterios de aceptación
- [x] Un solo CSV válido en `data/` → `csv validate` sale con 0 y nombra el archivo.
- [x] Un solo CSV con errores → exit 1 y el JSON trae `archivo: data/<nombre>.csv`.
- [x] Dos CSV → exit 2 y el mensaje nombra los dos; `csv validate <nombre>` sigue funcionando.
- [x] `data/` vacía, sin `.csv` o inexistente → exit 2 con la indicación de la plantilla.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_csv_cmd.py -q
uv run campaigns csv validate --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Pedido del usuario (2026-10-16). Con varios CSV se mantiene el error de T-021 en lugar de validarlos todos, para que `csv validate` y `s3 upload` sin argumento elijan siempre el mismo archivo.
- **Cierre (2026-10-16):** verificación local en verde (424 pruebas, cobertura 97 %; ruff y mypy). Probado con `data/campaigns-test.csv`.
