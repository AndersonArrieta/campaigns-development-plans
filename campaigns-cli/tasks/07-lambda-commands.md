# T-07 — Comandos `lambda`

- **Grupo:** `lambda`
- **Secciones del plan:** §2.1, §6, D-5
- **Depende de:** T-03, T-05

## Objetivo

Invocar `ingester_Lambda` y `scheduler_Lambda` de forma aislada (sin esperar al trigger real) y cualquier otra Lambda con un payload propio, mostrando la respuesta y el final de su log.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/lambda_service.py` | `LambdaService(client)` con `invoke(name, payload, tail)` y constructores de eventos `s3_put_event(bucket, key)` y `scheduled_event()`. |
| `src/campaigns_cli/commands/lambda_cmd.py` | Subgrupo `lambda` con `invoke`. |
| `src/campaigns_cli/events/` | Plantillas JSON de eventos (S3 `ObjectCreated:Put`, EventBridge `Scheduled Event`). |
| `tests/test_lambda_service.py` | Pruebas con `botocore.stub.Stubber`. |

## Pasos

1. Firma del comando:
   ```text
   campaigns lambda invoke ingester  --s3-key campaigns/input/campaign.csv [--tail]
   campaigns lambda invoke scheduler [--payload evento.json] [--tail]
   campaigns lambda invoke <nombre-o-arn> --payload evento.json [--tail] [--async]
   ```
   - `ingester` y `scheduler` son alias que resuelven a `INGESTER_LAMBDA_NAME` / `SCHEDULER_LAMBDA_NAME`.
2. Evento S3 sintético para el ingester: estructura `Records[0].eventSource = "aws:s3"`, `eventName = "ObjectCreated:Put"`, `s3.bucket.name = CAMPAIGNS_INPUT_BUCKET`, `s3.object.key = <key>` (URL-encoded como lo envía S3), `size` y `eTag` tomados de `head_object`. Verificar antes con `head_object` que el archivo existe (si no, sugerir `s3 upload`).
   > Confirmar con el código del ingester qué campos del evento lee y si su trigger es S3 directo, SQS o EventBridge; ajustar la plantilla.
3. Evento del scheduler: plantilla EventBridge `Scheduled Event` (o la que realmente usa su trigger; confirmar).
4. Invocación:
   - Síncrona por defecto: `InvocationType="RequestResponse"`; con `--tail` → `LogType="Tail"` y decodificar `LogResult` (base64, últimos 4 KB).
   - `--async` → `InvocationType="Event"`; solo se muestra el `StatusCode` 202.
   - Mostrar `StatusCode`, `FunctionError` (si existe), `ExecutedVersion` y el payload de respuesta formateado.
   - Exit code 1 si hay `FunctionError`.
5. Bloqueado en prod (`ensure_not_prod`).

## Pruebas

- Con `Stubber`: `invoke` envía el nombre y el payload esperados; con `--tail` decodifica `LogResult`.
- Respuesta con `FunctionError="Unhandled"` → exit code 1 y el mensaje de error visible.
- `s3_put_event` → estructura igual a un evento real (comparar con un fixture JSON).
- `invoke ingester` con una key inexistente (moto S3) → error de uso con sugerencia.
- Bloqueado con `CAMPAIGNS_ENV=prod`.

> moto necesita Docker para ejecutar Lambdas; por eso estas pruebas usan `Stubber` y no moto.

## Criterios de terminado

- [ ] `campaigns lambda invoke ingester --s3-key <key> --tail` procesa el CSV en dev y muestra su log.
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
