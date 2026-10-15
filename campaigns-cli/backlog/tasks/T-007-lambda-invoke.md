---
id: T-007
aliases: [T-007]
title: "Comando lambda invoke (ingester y genérico)"
status: backlog
priority: P2
epic: E-ingesta
estimate: M
depends_on: [T-003, T-005, T-019]
type: task
origin: tasks/07-lambda-commands.md
created: 2026-10-13
---

# T-007 — Comando `lambda invoke` (ingester y genérico)

## Objetivo
Invocar `ingester_Lambda` de forma aislada (sin esperar al trigger real) y cualquier otra Lambda con un payload propio, mostrando la respuesta y el final de su log ([ADR-0005](../../docs/adr/0005-ingesta-por-s3-y-por-invocacion.md): soportar subida a S3 e invocación directa).

El scheduler se invoca con `scheduler run` ([[T-019-scheduler-invoke|T-019]]). Esta tarjeta reutiliza su `LambdaService` y su política de reintentos: invocación síncrona, sin reintentos del SDK, y reintento solo de los errores en los que la función no llegó a correr.

## Archivos a crear/modificar
- `src/campaigns_cli/services/lambda_service.py` — (creado en T-019) agregar `s3_put_event(bucket, key, size, etag)`
- `src/campaigns_cli/events/s3_put.json` — plantilla del evento S3
- `src/campaigns_cli/commands/lambda_cmd.py` — subgrupo `lambda`
- `src/campaigns_cli/main.py` — registrar el subgrupo `lambda`
- `tests/fixtures/s3_put_event.json`, `tests/test_lambda_service.py` (ampliar), `tests/test_lambda_cmd.py`
- `docs/comandos.md`, `docs/recursos-aws.md`, `docs/README.md` (estado del grupo `lambda`)
- `docs/adr/0005-ingesta-por-s3-y-por-invocacion.md` — pasarla a `accepted` o reemplazarla

## Tareas
- [ ] Confirmar en el código de `ingester_Lambda` qué trigger usa (S3 directo, SQS o EventBridge) y qué campos del evento leen; ajustar las plantillas.
- [ ] Cerrar [ADR-0005](../../docs/adr/0005-ingesta-por-s3-y-por-invocacion.md): `accepted` si se confirma, o un ADR nuevo que la reemplace.
- [ ] `lambda invoke ingester --s3-key KEY [--tail]`: verifica con `head_object` que la key existe (si no, error de uso que sugiere `s3 upload`) y arma el evento `ObjectCreated:Put` con `size` y `eTag` reales y la key URL-encoded.
- [ ] `lambda invoke <nombre-o-arn> --payload evento.json [--tail]`.
- [ ] Siempre síncrona (`RequestResponse`) con `LambdaService.invoke_once` de T-019; sin `--async`, porque en modo `Event` Lambda reintenta sola y re-ejecuta la función. `--tail` → `LogType="Tail"` y decodificar `LogResult`.
- [ ] Mostrar `StatusCode`, `FunctionError`, `ExecutedVersion` y el payload de respuesta; exit code 1 si hay `FunctionError`.
- [ ] Bloqueado en prod (`ensure_not_prod`).

## Criterios de aceptación
- [ ] Con `Stubber`: `invoke` envía el nombre y el payload esperados; con `--tail` decodifica `LogResult`.
- [ ] `FunctionError="Unhandled"` → exit code 1 y el error visible.
- [ ] `s3_put_event` coincide con `tests/fixtures/s3_put_event.json`.
- [ ] `invoke ingester` con una key inexistente (moto S3) → exit code 2 con sugerencia.
- [ ] Con `CAMPAIGNS_ENV=prod` → bloqueado (exit 2).

## Verificación
```bash
uv run pytest tests/test_lambda_service.py tests/test_lambda_cmd.py -q
uv run campaigns lambda invoke --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Notas
- moto necesita Docker para ejecutar Lambdas: estas pruebas usan `botocore.stub.Stubber` o un cliente falso, como `test_config_check.py`.
- Invocar las lambdas reales de dev (`--s3-key <key> --tail`) produce envíos reales y requiere confirmación del usuario; se ejercita en [[T-013-trace-aguas-abajo|T-013]]; el scheduler, con `scheduler run` de [[T-019-scheduler-invoke|T-019]].
