---
id: T-021
aliases: [T-021]
title: "s3 upload sin argumento: subir el único CSV de data/"
status: done
priority: P2
epic: E-ingesta
estimate: S
depends_on: [T-004, T-005]
type: task
affects: [T-005]
created: 2026-10-16
---

# T-021 — `s3 upload` sin argumento: subir el único CSV de `data/`

## Objetivo
El flujo de prueba es armar un CSV a mano en `campaigns-cli/data/` y subirlo. Hoy
[[T-005-s3-commands|T-005]] exige `s3 upload <archivo>`. Con esta tarjeta, `uv run campaigns s3 upload`
sin argumento toma el CSV de `data/`. Como subir dispara envíos reales, solo lo hace si hay
**exactamente uno**: con varios no adivina cuál subir.

## Archivos a crear/modificar
- `src/campaigns_cli/services/csv_service.py` — `find_single_csv(directory)`: el único `*.csv` de `data/` o `UsageError`
- `src/campaigns_cli/commands/s3_cmd.py` — `archivo` opcional en `upload`
- `tests/test_csv_service.py`, `tests/test_s3_cmd.py`
- `docs/comandos.md`, `README.md`

## Tareas
- [x] `s3 upload [archivo]`: sin `archivo`, busca los `*.csv` directamente en `data/` (sin subcarpetas).
  - Uno → lo usa y muestra cuál (`Archivo: data/<nombre>.csv`) antes de validar y subir.
  - Varios → `UsageError` (exit 2) con la lista ordenada y el aviso de pasar el nombre; no sube nada.
  - Ninguno o sin carpeta `data/` → `UsageError` (exit 2) que indica copiar `templates/plantilla.csv` a `data/`.
- [x] Con `archivo`, el comportamiento de T-005 no cambia.
- [x] La validación, `--key` y `--no-validate` funcionan igual con el archivo encontrado.
- [x] Actualizar `docs/comandos.md` y `README.md`.

## Criterios de aceptación
- [x] Un solo CSV en `data/` → `s3 upload` lo sube con la key por defecto (moto).
- [x] Dos CSV en `data/` → exit 2, el mensaje nombra los dos y el bucket queda vacío.
- [x] `data/` vacía, con solo archivos que no son `.csv`, o inexistente → exit 2 con la indicación de la plantilla.
- [x] Un CSV en una subcarpeta de `data/` no cuenta.
- [x] `s3 upload <archivo>` sigue funcionando con varios CSV en `data/`.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_csv_service.py tests/test_s3_cmd.py -q
uv run campaigns s3 upload --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Decisión del usuario (2026-10-16): con varios CSV, error en lugar de tomar el más reciente o mostrar un menú. Así no se sube por accidente un CSV viejo olvidado en `data/`.
- `csv validate` sigue exigiendo el archivo; no se pidió el mismo cambio.
- **Cierre (2026-10-16):** verificación local en verde (418 pruebas, cobertura 97 %, `s3_cmd.py` al 100 %; ruff y mypy).
