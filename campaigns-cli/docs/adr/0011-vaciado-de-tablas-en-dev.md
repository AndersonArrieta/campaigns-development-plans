---
id: ADR-0011
title: "Las tablas de dev son de uso exclusivo de las pruebas: dynamo clean las vacía por completo"
status: superseded
date: 2026-10-16
supersedes:
superseded_by: ADR-0012
---

# ADR-0011 — Las tablas de dev son de uso exclusivo de las pruebas: `dynamo clean` las vacía por completo

## Contexto
Entre una prueba y la siguiente quedan en DynamoDB las filas del CSV anterior: las que escribe el
ingester, las que agrega `platform_campaigns_ms` al reprogramar (una fila nueva con el mismo
`notification_id`, sin borrar la anterior) y las cargas de la tabla de logs, incluidas las `UNKNOWN`.
`dynamo purge` ([T-012](../../backlog/tasks/T-012-dynamo-purge.md)) solo borra filas de campañas de
`CLI_TEST_APP_ID` y no toca la tabla de logs, así que no deja las tablas en un estado conocido.

Las tablas de campañas y de logs de dev las usa solo el autor de las pruebas: vaciarlas no
afecta a nadie más.

## Decisión
- `dynamo clean` **vacía por completo** las tablas indicadas (`--table campaigns|logs|all`, por
  defecto `all`): todas las filas de todos los `app_id`. Con `--campaign-id` borra solo las filas de
  ese CSV en las dos tablas, incluidas sus reprogramaciones y su carga `UNKNOWN`.
- El borrado es por clave: `scan` paginado con `ProjectionExpression` y `batch_write_item` en lotes
  de 25 con reintento de `UnprocessedItems`. No se usan `DeleteTable`/`CreateTable`: se perderían el
  TTL, los streams y los permisos de la tabla, y la CLI necesitaría permisos de administración.
- Protecciones: bloqueado en prod (`ensure_not_prod`), plan visible antes de borrar (filas por tabla y
  `app_id`, reprogramadas, `PENDIENTE` y `EN_CURSO`), `confirm_destructive` con el entorno y el
  nombre de cada tabla, `--dry-run`, y un `scan` de verificación al final (exit 1 si quedan filas).
- **Cambio en el triage del backlog:** que `dynamo clean` sin `--campaign-id` borre filas de
  cualquier `app_id` en dev es el comportamiento esperado, no un `P0`. Sigue siendo `P0` que
  `clean` escriba en prod o que `clean --campaign-id` borre filas de otro `campaign_id`.

## Consecuencias
- Antes de cada prueba se puede partir de tablas vacías; `dynamo purge` queda para borrar los datos
  de `CLI_TEST_APP_ID` de un CSV sin tocar los de otras apps.
- Si las tablas de dev pasan a compartirse con otro equipo, este ADR se reemplaza: el vaciado
  completo dejaría de ser seguro.
- Las filas que el ingester o el ms escriban durante el borrado pueden quedar; la verificación final
  las informa como restantes.
- Necesita `dynamodb:BatchWriteItem` sobre las dos tablas.
- Origen: [T-020](../../backlog/tasks/T-020-dynamo-historial-y-limpieza.md).
