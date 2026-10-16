---
id: T-005
aliases: [T-005]
title: "Comandos s3: upload, ls, get, rm"
status: done
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
- [x] Todos los comandos llaman a `settings.require("campaigns_input_bucket")` y usan `AwsClients`.
- [x] `s3 upload <archivo> [--key KEY] [--no-validate]`:
  - Valida con `csv_service.validate_csv` ([[T-004-csv-generate-validate|T-004]]) antes de subir; con errores no sube y sale con 1.
  - Key por defecto: `CAMPAIGNS_INPUT_PREFIX + <nombre del archivo>` (el prefijo puede ir vacío: raíz del bucket).
  - `ContentType="text/csv"`; muestra bucket, key, `ETag`, `VersionId` y hora de subida (Colombia).
  - Bloqueado en prod (`ensure_not_prod`): subir dispara envíos reales.
- [x] `s3 ls [--prefix P] [--limit N]`: paginador `list_objects_v2`; key, tamaño y última modificación, de la más reciente a la más antigua.
- [x] `s3 get <key> [-o archivo]`: sin `-o`, imprime el contenido en stdout.
- [x] `s3 rm <key>`: `ensure_not_prod` + `confirm_destructive`; si `CAMPAIGNS_INPUT_PREFIX` no está vacío, solo keys dentro del prefijo.

## Criterios de aceptación
- [x] `upload` con moto → objeto con la key esperada y `ContentType` `text/csv`.
- [x] `upload` de un CSV inválido → nada subido y exit code 1; con `--no-validate` sí se sube.
- [x] `ls` con más de 1000 objetos devuelve todos (o hasta `--limit`).
- [x] `get` sin `-o` → contenido en stdout.
- [x] `rm` fuera del prefijo → error de uso (exit 2); dentro, con `--yes` → borrado.
- [x] `upload` y `rm` con `CAMPAIGNS_ENV=prod` → bloqueados (exit 2).

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
- **Cierre (2026-10-16):** verificación local en verde (411 pruebas, cobertura 97 %; `s3_service.py` y `s3_cmd.py` al 100 %; ruff y mypy). No se subió nada al bucket real: la prueba en dev sigue en T-009.
- **Carpeta `data/` (pedido del usuario):** `upload` resuelve el archivo como `csv validate` ([[T-004-csv-generate-validate|T-004]]): la ruta indicada o su nombre dentro de `campaigns-cli/data/`. La plantilla versionada está en `templates/plantilla.csv`.
- `CAMPAIGNS_INPUT_PREFIX` se normaliza con `/` final (`entrada` → `entrada/`) para que la key por defecto no quede pegada al nombre del archivo.
- `upload` valida contra la hora actual de Colombia: un CSV con `fecha_fin` en el pasado no se sube. Los avisos (horas ya pasadas, días fuera del rango) se muestran sin frenar la subida.
- `rm` hace `head_object` antes de confirmar: `delete_object` sobre una key inexistente no falla en S3, así que sin esa comprobación el comando diría que borró algo que no existía (sale con 3).
- El ingester borra el CSV del bucket cuando termina de procesarlo (`processor.py` → `delete_data_file`): documentado en `docs/recursos-aws.md`. `s3 ls` no sirve para comprobar una subida pasados unos segundos; para eso está la tabla de logs.
