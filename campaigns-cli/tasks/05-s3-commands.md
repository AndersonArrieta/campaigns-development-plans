# T-05 — Comandos `s3`

- **Grupo:** `s3`
- **Secciones del plan:** §2.1, §6
- **Depende de:** T-03

## Objetivo

Operar sobre el bucket de entrada del ingester: subir CSV (que dispara la ingesta real), listar, descargar y borrar archivos de prueba.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/s3_service.py` | `S3Service(client, bucket, prefix)` con `upload`, `list`, `download`, `delete`. |
| `src/campaigns_cli/commands/s3_cmd.py` | Subgrupo `s3` con `upload`, `ls`, `get`, `rm`. |
| `tests/test_s3_service.py` | Pruebas con moto. |

## Pasos

1. Todos los comandos llaman a `settings.require("campaigns_input_bucket")`.
2. `s3 upload <archivo> [--key KEY] [--no-validate]`:
   - Por defecto valida el CSV con `csv_service.validate_csv` (T-04) antes de subirlo; si hay errores, no sube y sale con 1.
   - Key por defecto: `CAMPAIGNS_INPUT_PREFIX + <nombre del archivo>`.
   - `ContentType="text/csv"`.
   - Muestra bucket, key, `ETag`, `VersionId` (si el bucket tiene versionado) y la hora de subida (útil luego para `logs search --since`).
   - Bloqueado en prod (`ensure_not_prod`): subir dispara envíos reales.
3. `s3 ls [--prefix P] [--limit N]`: paginar con `get_paginator("list_objects_v2")`; columnas key, tamaño, última modificación; ordenar por fecha descendente.
4. `s3 get <key> [-o archivo]`: descarga; sin `-o`, imprime el contenido en stdout.
5. `s3 rm <key>`: `ensure_not_prod` + `confirm_destructive`; solo permite borrar keys dentro de `CAMPAIGNS_INPUT_PREFIX`.

## Pruebas

- `upload` con moto → el objeto existe con la key esperada y `ContentType` `text/csv`.
- `upload` de un CSV inválido → no se sube nada y exit code 1; con `--no-validate` sí se sube.
- `ls` con más de 1000 objetos → la paginación los devuelve todos (o hasta `--limit`).
- `get` sin `-o` → el contenido aparece en stdout.
- `rm` fuera del prefijo → error de uso; dentro del prefijo con `--yes` → objeto borrado.
- `upload` y `rm` con `CAMPAIGNS_ENV=prod` → bloqueados.

## Criterios de terminado

- [ ] Subir `csv-test.csv` en dev con `campaigns s3 upload` dispara el ingester (verificable en sus logs).
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
