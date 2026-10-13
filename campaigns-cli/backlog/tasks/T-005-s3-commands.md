---
id: T-005
aliases: [T-005]
title: "Comandos s3: upload, ls, get, rm"
status: backlog
priority: P1
epic: E-ingesta
estimate: M
depends_on: [T-003, T-004]
type: task
origin: tasks/05-s3-commands.md
created: 2026-10-13
---

# T-005 — Comandos `s3`: `upload`, `ls`, `get`, `rm`

## Objetivo
Operar sobre el bucket de entrada del ingester: subir CSV (lo que dispara la ingesta real), listar, descargar y borrar archivos de prueba.

## Archivos a crear/modificar
- `src/campaigns_cli/services/s3_service.py` — `S3Service(client, bucket, prefix)` con `upload`, `list`, `download`, `delete`
- `src/campaigns_cli/commands/s3_cmd.py` — subgrupo `s3`
- `src/campaigns_cli/main.py` — registrar el subgrupo `s3`
- `tests/test_s3_service.py`, `tests/test_s3_cmd.py`
- `docs/comandos.md`, `docs/recursos-aws.md`, `docs/README.md` (estado del grupo `s3`)

## Tareas
- [ ] Todos los comandos llaman a `settings.require("campaigns_input_bucket")` y usan `AwsClients`.
- [ ] `s3 upload <archivo> [--key KEY] [--no-validate]`:
  - Valida con `csv_service.validate_csv` ([[T-004-csv-generate-validate|T-004]]) antes de subir; con errores no sube y sale con 1.
  - Key por defecto: `CAMPAIGNS_INPUT_PREFIX + <nombre del archivo>` (el prefijo puede ir vacío: raíz del bucket).
  - `ContentType="text/csv"`; muestra bucket, key, `ETag`, `VersionId` y hora de subida (Colombia).
  - Bloqueado en prod (`ensure_not_prod`): subir dispara envíos reales.
- [ ] `s3 ls [--prefix P] [--limit N]`: paginador `list_objects_v2`; key, tamaño y última modificación, de la más reciente a la más antigua.
- [ ] `s3 get <key> [-o archivo]`: sin `-o`, imprime el contenido en stdout.
- [ ] `s3 rm <key>`: `ensure_not_prod` + `confirm_destructive`; si `CAMPAIGNS_INPUT_PREFIX` no está vacío, solo keys dentro del prefijo.

## Criterios de aceptación
- [ ] `upload` con moto → objeto con la key esperada y `ContentType` `text/csv`.
- [ ] `upload` de un CSV inválido → nada subido y exit code 1; con `--no-validate` sí se sube.
- [ ] `ls` con más de 1000 objetos devuelve todos (o hasta `--limit`).
- [ ] `get` sin `-o` → contenido en stdout.
- [ ] `rm` fuera del prefijo → error de uso (exit 2); dentro, con `--yes` → borrado.
- [ ] `upload` y `rm` con `CAMPAIGNS_ENV=prod` → bloqueados (exit 2).

## Verificación
```bash
uv run pytest tests/test_s3_service.py tests/test_s3_cmd.py -q
uv run campaigns s3 --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- La prueba real (subir `csv-test.csv` en dev y ver que el ingester lo procesa) se hace en [[T-009-trace-run|T-009]]; subir al bucket de dev dispara la ingesta y requiere confirmación del usuario.
- Depende de [[T-004-csv-generate-validate|T-004]] porque `upload` reutiliza `validate_csv`.
