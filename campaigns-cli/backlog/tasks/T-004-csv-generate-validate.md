---
id: T-004
aliases: [T-004]
title: "Comandos csv: generate y validate"
status: done
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
| `canal` | Obligatorio. Valores usados por `Platform_test`: `WhatsApp` y `msteams` (datasets `whatsapp/DataSet.csv` y `teams/DataSet.csv`); confirmar la lista con el ingester. |
| `usuario` | Obligatorio. Para `WhatsApp`: solo dígitos, con indicativo de país. Para `msteams`: email del usuario. |
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
- [x] Contrastar las reglas marcadas "confirmar" con el validador de `ingester_Lambda` (repo `NU0284001_Artemis_Chatbots_Platform_MR`) y citar el archivo de origen en un comentario de `csv_service.py`.
- [x] `csv generate --users U1,U2 --canal WhatsApp --fecha 13/10/2026 [--fecha-fin] --hora 10 --nodo N-03-99-10 [--app-id] [--dias] [--parametros k=v] [-o archivo]`:
  - `--app-id` por defecto `CLI_TEST_APP_ID` (para que `dynamo purge` pueda limpiar).
  - `--fecha` acepta `hoy` y `mañana`; `dias` se calcula de la fecha si no se pasa `--dias`.
  - `--hora` acepta `+N` (hora actual de Colombia + N).
  - Sin `-o`, escribe `campaign-<timestamp>.csv`.
  - Separador `;`, UTF-8 sin BOM (confirmar), salto de línea `\n`; módulo `csv` de la librería estándar.
- [x] `csv validate <archivo>`: encabezado exacto y en orden, separador `;`, columnas por fila y reglas de la tabla; problemas por fila y columna; exit code 1 si hay errores; salida JSON con `--output json`.
- [x] Registrar el subgrupo en `main.py`.

## Criterios de aceptación
- [x] `validate` sobre `tests/fixtures/csv-test.csv` → sin problemas, exit code 0.
- [x] Ida y vuelta: `generate` → `validate` del archivo generado → sin problemas.
- [x] Separador `,`, fecha `2026-10-13`, `fecha_inicio > fecha_fin`, hora `24`, día `martez` (el ingester acepta `tuesday`, ver Notas) o columna faltante → un problema por caso con fila y columna, exit code 1.
- [x] `--fecha hoy` sin `--dias` → `dias` es el día de la semana de hoy (hora Colombia).
- [x] `csv` no crea clientes AWS ni exige credenciales.

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
- **Cierre (2026-10-16):** verificación local en verde (387 pruebas, cobertura 97 %, ruff y mypy). Reglas contrastadas con `ingester_Lambda/src/libs/source_data_management.py`, `src/models/notification.py`, `src/controllers/processor.py` e `ingester_Conf/ingester.yaml` (citados en `csv_service.py`). Diferencias con la tabla propuesta:
  - `dias` acepta inglés además de español sin tildes: `tuesday` es válido, así que el criterio usa `martez`.
  - `usuario` no depende del canal: teléfono `^[0-9]{11,12}$` o email en minúscula (el regex del ingester no tiene mayúsculas) con cualquier canal.
  - `canal` admite `msteams`, `email`, `sms`, `push` y `whatsapp`, sin distinguir mayúsculas.
  - `fecha_fin` no puede ser anterior a hoy (Colombia); varias horas y días van separados por `,` (`10,11,12`); `parametros` es `clave:valor` separados por `,` (`generate` acepta `clave=valor`).
  - El encabezado solo exige las 9 columnas: el orden y las columnas extra dan aviso, no error.
  - Se agregaron avisos de lo que el ingester omite sin error (días fuera del rango, horas ya pasadas).
- **Carpeta `data/` (pedido del usuario):** los CSV de prueba van en `campaigns-cli/data/`, ignorada por git: `generate` escribe en `data/` por defecto (`data/campaign-<AAAAMMDD-HHMMSS>.csv`) y `validate` busca en `data/` si la ruta no existe. La plantilla versionada es `templates/plantilla.csv`, fuera de `data/` a pedido del usuario.
- `tests/fixtures/csv-test.csv` copia el formato de `../csv-test.csv` (CRLF, horas `10,11,12`) con fecha 25/12/2099: con la fecha original, `validate` fallaría desde el día siguiente por `fecha_fin` en el pasado.
- UTF-8 sin BOM y salto `\n` confirmados: el ingester decodifica con `utf-8-sig` y acepta CRLF.
