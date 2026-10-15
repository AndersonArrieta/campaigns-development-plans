---
id: T-019
aliases: [T-019]
title: "Comando scheduler run: disparar scheduler_Lambda a demanda sin reintentos que la re-ejecuten"
status: todo
priority: P1
epic: E-ingesta
estimate: M
depends_on: [T-003, T-006, T-008]
type: task
created: 2026-10-15
---

# T-019 — Comando `scheduler run`: disparar `scheduler_Lambda` a demanda

## Objetivo
Hoy hay que esperar a que la regla de EventBridge invoque `scheduler_Lambda` cada hora en punto.
Este comando la invoca desde la CLI **cada vez que se pida**, para probar el tramo
tabla de campañas → Kafka → `platform_campaigns_ms` sin esperar. Una invocación pedida por el
usuario debe producir **exactamente una ejecución**: ningún reintento (del SDK ni del servicio
Lambda) puede volver a ejecutar la función.

Se separa de [[T-007-lambda-invoke|T-007]] porque no necesita S3 ni CSV (T-004/T-005) y queda
desbloqueada ya. T-007 reutiliza el `LambdaService` de esta tarjeta para ingester y genérico.

## Comportamiento del scheduler (confirmado en su código)
- `app.py:handler` **ignora el evento**, salvo `{"type": "health"}`, que solo prueba Kafka.
  Cualquier otro payload (`{}`, el `Scheduled Event` de EventBridge) hace el despacho.
- Procesa **solo la hora en curso en Colombia**: `datetime_lib.get_current_datetime()` →
  `YYYY-MM-DD HH:00:00` UTC-5 y `query` a esa partición de la tabla de campañas. No se puede
  pedir otra hora.
- **No es idempotente.** No borra ni marca las filas: cada ejecución vuelve a publicar en Kafka
  **todas** las notificaciones de esa hora, incluidas las de otros equipos en dev.
- Responde `{"statusCode", "message", "execution_datetime", "detail": {"successful",
  "failed", "total"}}` y deja `Execution result: {...}` en su log.
- El ingester acepta filas para la hora en curso (`notification.py:94-95` compara con la hora
  en punto actual), así que el flujo de prueba es: CSV con la hora actual → `scheduler run`.
  Las filas que se agregan después de que EventBridge corrió en esa hora no se envían solas;
  esta es la única forma de despacharlas.

## Diseño: una invocación = una ejecución
| Riesgo | Mitigación |
|---|---|
| Reintentos de botocore. `CLIENT_CONFIG` (`aws.py:21`) usa `standard` con 5 intentos; un `ReadTimeoutError` reenvía `Invoke` mientras la primera ejecución sigue corriendo. | Cliente Lambda **propio** para invocar: `Config(retries={"total_max_attempts": 1}, read_timeout=<Timeout de la función> + 30, connect_timeout=10, tcp_keepalive=True)`. El `Timeout` se lee con `get_function_configuration` antes de invocar. |
| Reintentos del servicio Lambda. En invocación asíncrona (`Event`), Lambda reintenta hasta 2 veces si la función falla. | Solo `InvocationType="RequestResponse"`, que Lambda nunca reintenta. **No** se ofrece `--async`. |
| Errores transitorios en los que AWS garantiza que no hubo ejecución. | Reintento controlado por la CLI (máx. 3, backoff 1-2-4 s) **solo** para `TooManyRequestsException`, `EndpointConnectionError` y `ConnectTimeoutError`. |
| Errores ambiguos: la Lambda pudo haber corrido (`ReadTimeoutError`, `ServiceException`/5xx, conexión cortada después de enviar). | **No se reintenta.** Resultado `DESCONOCIDO`, exit 3; la CLI busca en el log group del scheduler (`LogsService.events`) un `Execution result` posterior a `t0` y lo muestra si aparece. |
| Doble ejecución por doble Enter / dos terminales. | Fuera de alcance: cada comando confirmado es una ejecución intencional. La confirmación previa muestra cuántas filas se van a reenviar. |

## Archivos a crear/modificar
- `src/campaigns_cli/aws.py` — `lambda_invoke_client(read_timeout)`: cliente sin reintentos, separado de `lambda_`
- `src/campaigns_cli/services/lambda_service.py` — `LambdaService` con `function_timeout(name)`, `invoke_once(name, payload, tail) -> InvokeResult` y la clasificación de errores (`RETRYABLE`, `AMBIGUOUS`)
- `src/campaigns_cli/services/scheduler_service.py` — `current_partition()` (hora Colombia, igual que la Lambda), `preview(table)` (filas de la partición por `app_id`), `run(...)`
- `src/campaigns_cli/commands/scheduler_cmd.py` — subgrupo `scheduler` con `run` y `health`
- `src/campaigns_cli/main.py` — registrar el subgrupo `scheduler`
- `tests/test_lambda_service.py`, `tests/test_scheduler_service.py`, `tests/test_scheduler_cmd.py`
- `docs/comandos.md`, `docs/recursos-aws.md` (sección Lambdas), `docs/configuracion.md` (permisos IAM)
- `docs/adr/0010-invocacion-sin-reintentos.md` — invocación síncrona sin reintentos del SDK

## Tareas
- [ ] `scheduler run [--tail] [--yes]`:
  1. `ensure_not_prod`; exige `SCHEDULER_LAMBDA_NAME` y `CAMPAIGNS_TABLE_NAME`.
  2. Calcula la partición actual (`YYYY-MM-DD HH:00:00`, UTC-5) y hace `query` a la tabla de campañas (`CampaignsTable.list_range` de [[T-006-dynamo-lectura|T-006]]).
  3. Muestra el total por `app_id` y avisa si hay filas cuyo `app_id` no es `CLI_TEST_APP_ID` ("se reenviarán notificaciones de otros equipos").
  4. Con 0 filas, avisa que el scheduler no enviará nada y pide confirmación igual (sirve para probar la invocación).
  5. Pide confirmación (`confirm_destructive`); `--yes` la omite.
  6. Lee el `Timeout` de la función e invoca una vez con `{}`.
  7. Muestra `StatusCode`, `FunctionError`, `ExecutedVersion`, el `RequestId` (`ResponseMetadata`) y `detail` (`total/successful/failed`); con `--tail`, decodifica `LogResult` (últimos 4 KB).
- [ ] Advertencia si la partición cambia entre la vista previa y la invocación (se invoca en el minuto 59): el scheduler procesará la hora siguiente.
- [ ] `scheduler health`: invoca con `{"type": "health"}` (no despacha nada, no pide confirmación) y muestra si Kafka responde.
- [ ] Exit codes: 0 OK; 1 si hay `FunctionError` o `detail.failed > 0`; 3 si el resultado es `DESCONOCIDO` o hubo un error de AWS no reintentable.
- [ ] `--output json` devuelve `{partition, preview, invocation: {status_code, function_error, request_id, payload}, outcome}`.
- [ ] Mensaje claro para `AccessDeniedException` en `lambda:InvokeFunction` ("las credenciales de solo lectura no pueden invocar la Lambda").
- [ ] Documentar en `docs/configuracion.md` los permisos mínimos: `lambda:GetFunctionConfiguration`, `lambda:InvokeFunction` sobre el ARN del scheduler, `dynamodb:Query` sobre la tabla de campañas y `logs:FilterLogEvents` sobre su log group.
- [ ] Escribir ADR-0010 y actualizar `docs/`.
- [ ] Ejecutar en dev con un CSV de `CLI_TEST_APP_ID` para la hora actual y guardar la salida en `evidencias/t019/` (sin credenciales ni ARNs completos).

## Criterios de aceptación
- [ ] El cliente de invocación tiene `total_max_attempts == 1` y `read_timeout >= Timeout + 30` (test sobre su `Config`).
- [ ] Con `Stubber`: `ReadTimeoutError` → **una sola** llamada a `Invoke`, resultado `DESCONOCIDO`, exit 3.
- [ ] Con `Stubber`: `TooManyRequestsException` y luego éxito → 2 llamadas a `Invoke`, exit 0.
- [ ] `ServiceException` (5xx) → una sola llamada, `DESCONOCIDO`.
- [ ] Respuesta con `FunctionError="Unhandled"` → exit 1 y el error visible; con `detail.failed > 0` → exit 1.
- [ ] Vista previa (moto DynamoDB) con filas de `others-test` y de otra app → la advertencia nombra la otra app; sin `--yes` y respondiendo "no" → no se llama a `Invoke`, exit 0.
- [ ] `current_partition()` con un reloj fijo `2026-10-15 03:30 UTC` → `2026-10-14 22:00:00`.
- [ ] Ejecutar `scheduler run --yes` dos veces seguidas → dos invocaciones (no hay bloqueo entre corridas).
- [ ] `scheduler health` envía `{"type": "health"}` y no pide confirmación.
- [ ] `AccessDeniedException` → exit 3 con el mensaje de permisos.
- [ ] Con `CAMPAIGNS_ENV=prod` → bloqueado (exit 2) para `run` y `health`.

## Verificación
```bash
# desde campaigns-cli/, con UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli
uv run pytest tests/test_lambda_service.py tests/test_scheduler_service.py tests/test_scheduler_cmd.py -q
uv run campaigns scheduler run --help
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
# en dev (requiere confirmación del usuario: publica en Kafka todas las filas de la hora en curso)
mkdir -p evidencias/t019
uv run campaigns scheduler health 2>&1 | tee evidencias/t019/health.txt
uv run campaigns scheduler run --tail 2>&1 | tee evidencias/t019/run.txt
```

## Notas
- **Credenciales de solo lectura no alcanzan.** `lambda:InvokeFunction` es una acción de escritura: no la incluyen `ReadOnlyAccess` ni `AWSLambda_ReadOnlyAccess`. Se necesita un rol o política de dev con `InvokeFunction` sobre el ARN del scheduler. La vista previa (`dynamodb:Query`) y `GetFunctionConfiguration` sí funcionan con solo lectura.
- moto necesita Docker para ejecutar Lambdas: estas pruebas usan `botocore.stub.Stubber` o un cliente falso, como `test_config_check.py`.
- Relación con EventBridge: su próxima corrida (a la hora siguiente) procesa **otra** partición, así que `scheduler run` no duplica lo que hará EventBridge. Sí reenvía lo que EventBridge ya despachó en punto en la hora en curso.
- Los reenvíos duplicados aguas abajo son el problema que analiza `../idempotencia-campañas/`; esta CLI no lo resuelve, solo lo hace visible antes de invocar.
