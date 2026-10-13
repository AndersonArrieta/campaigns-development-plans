---
id: T-004
aliases: [T-004]
title: "Comandos csv: generate y validate"
status: todo
priority: P1
epic: E-csv
estimate: M
depends_on: [T-001]
type: task
origin: tasks/04-csv-commands.md
created: 2026-10-13
---

# T-004 — Comandos `csv`: `generate` y `validate`

## Objetivo
Generar CSV de campaña válidos para `ingester_Lambda` y validar archivos existentes, sin AWS. Es la entrada de `s3 upload` ([[T-005-s3-commands|T-005]]) y de `trace run` ([[T-009-trace-run|T-009]]).

Formato de referencia (`../csv-test.csv`):

```
app_id;canal;usuario;fecha_inicio;fecha_fin;dias;horas;nodo;parametros
others-test;WhatsApp;573232540390;13/10/2026;13/10/2026;martes;10;N-03-99-10;
```

| Columna | Regla de validación (propuesta) |
|---|---|
| `app_id` | Obligatorio, no vacío. |
| `canal` | Obligatorio. Valores conocidos: `WhatsApp`, `Teams` (confirmar lista con el ingester). |
| `usuario` | Obligatorio. Para `WhatsApp`: solo dígitos, con indicativo de país. |
| `fecha_inicio`, `fecha_fin` | `dd/mm/yyyy`; `fecha_inicio <= fecha_fin`. |
| `dias` | Días en español, en minúscula (`lunes`…`domingo`). Confirmar separador si hay varios. |
| `horas` | Entero 0–23. Confirmar separador si hay varias. |
| `nodo` | Obligatorio; patrón `N-\d{2}-\d{2}-\d{2}` (confirmar). |
| `parametros` | Opcional. Confirmar formato con el ingester. |

## Archivos a crear/modificar
- `src/campaigns_cli/services/csv_service.py` — `CampaignRow`, `generate_rows(...)`, `write_csv(rows, path)`, `validate_csv(path) -> list[ValidationIssue]`
- `src/campaigns_cli/commands/csv_cmd.py` — subgrupo `csv` con `generate` y `validate`
- `src/campaigns_cli/main.py` — registrar el subgrupo `csv`
- `tests/fixtures/csv-test.csv` — copia del CSV de referencia
- `tests/test_csv_service.py`, `tests/test_csv_cmd.py`
- `docs/comandos.md`, `docs/README.md` (estado del grupo `csv`)

## Tareas
- [ ] Contrastar las reglas marcadas "confirmar" con el validador de `ingester_Lambda` (repo `NU0284001_Artemis_Chatbots_Platform_MR`) y citar el archivo de origen en un comentario de `csv_service.py`.
- [ ] `csv generate --users U1,U2 --canal WhatsApp --fecha 13/10/2026 [--fecha-fin] --hora 10 --nodo N-03-99-10 [--app-id] [--dias] [--parametros k=v] [-o archivo]`:
  - `--app-id` por defecto `CLI_TEST_APP_ID` (para que `dynamo purge` pueda limpiar).
  - `--fecha` acepta `hoy` y `mañana`; `dias` se calcula de la fecha si no se pasa `--dias`.
  - `--hora` acepta `+N` (hora actual de Colombia + N).
  - Sin `-o`, escribe `campaign-<timestamp>.csv`.
  - Separador `;`, UTF-8 sin BOM (confirmar), salto de línea `\n`; módulo `csv` de la librería estándar.
- [ ] `csv validate <archivo>`: encabezado exacto y en orden, separador `;`, columnas por fila y reglas de la tabla; problemas por fila y columna; exit code 1 si hay errores; salida JSON con `--output json`.
- [ ] Registrar el subgrupo en `main.py`.

## Criterios de aceptación
- [ ] `validate` sobre `tests/fixtures/csv-test.csv` → sin problemas, exit code 0.
- [ ] Ida y vuelta: `generate` → `validate` del archivo generado → sin problemas.
- [ ] Separador `,`, fecha `2026-10-13`, `fecha_inicio > fecha_fin`, hora `24`, día `tuesday` o columna faltante → un problema por caso con fila y columna, exit code 1.
- [ ] `--fecha hoy` sin `--dias` → `dias` es el día de la semana de hoy (hora Colombia).
- [ ] `csv` no crea clientes AWS ni exige credenciales.

## Verificación
```bash
uv run pytest tests/test_csv_service.py tests/test_csv_cmd.py -q
uv run campaigns csv validate tests/fixtures/csv-test.csv
OUT="$(mktemp -d)/campaign.csv"
uv run campaigns csv generate --users 573232540390 --canal WhatsApp --fecha hoy --hora 10 --nodo N-03-99-10 -o "$OUT"
uv run campaigns csv validate "$OUT"
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- Que el ingester acepte en dev un CSV generado por la CLI se comprueba en [[T-009-trace-run|T-009]].
- Si no hay acceso al código del ingester, se dejan las reglas propuestas y se anota aquí qué quedó sin confirmar.
