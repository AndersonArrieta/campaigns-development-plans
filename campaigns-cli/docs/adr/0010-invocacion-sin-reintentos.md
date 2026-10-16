---
id: ADR-0010
title: "Invocación síncrona de Lambdas sin reintentos del SDK: una invocación = una ejecución"
status: accepted
date: 2026-10-16
supersedes:
---

# ADR-0010 — Invocación síncrona de Lambdas sin reintentos del SDK: una invocación = una ejecución

## Contexto
`scheduler_Lambda` no es idempotente: cada ejecución vuelve a publicar en Kafka todas las
notificaciones de la hora en curso, de todos los `app_id`. Una invocación pedida desde la CLI
([T-019](../../backlog/tasks/T-019-scheduler-invoke.md)) tiene que producir **exactamente una**
ejecución, y hay dos fuentes de reintentos que pueden repetirla sin que el usuario lo sepa:

- **botocore.** `CLIENT_CONFIG` (`aws.py`) usa el modo `standard` con 5 intentos. Si `Invoke` tarda
  más que el `read_timeout` (60 s por defecto), el SDK lanza `ReadTimeoutError` internamente y
  reenvía la petición mientras la primera ejecución sigue corriendo.
- **El servicio Lambda.** En invocación asíncrona (`InvocationType="Event"`) Lambda reintenta hasta
  2 veces si la función falla. En `RequestResponse` nunca reintenta.

## Decisión
- Solo `InvocationType="RequestResponse"`. La CLI **no** ofrece `--async`.
- Cliente Lambda propio para `Invoke` (`AwsClients.lambda_invoke_client(read_timeout)`), separado de
  `lambda_`: `retries={"mode": "standard", "total_max_attempts": 1}`,
  `read_timeout = Timeout de la función + 30 s` (leído con `GetFunctionConfiguration` antes de
  invocar), `connect_timeout=10` y `tcp_keepalive=True`.
- Clasificación de errores en `services/lambda_service.py`:
  - **Reintentables** (AWS garantiza que la función no corrió): `TooManyRequestsException`,
    `EndpointConnectionError`, `ConnectTimeoutError`. La CLI reintenta como máximo 3 veces con
    espera de 1, 2 y 4 s.
  - **Ambiguos** (la función pudo haber corrido): `ReadTimeoutError`, `ConnectionClosedError` y
    cualquier `HTTPClientError`, `ServiceException` o respuesta 5xx. **No se reintentan**: el resultado
    es `DESCONOCIDO` (exit 3) y la CLI busca en el log group de la función un `Execution result`
    posterior al inicio de la invocación.
  - El resto (`AccessDeniedException`, `ResourceNotFoundException`, parámetros inválidos) se propaga
    sin reintento; `AccessDeniedException` lleva un mensaje de permisos.
- Cada comando confirmado es una ejecución intencional: no hay bloqueo entre dos corridas seguidas
  (doble Enter o dos terminales quedan fuera de alcance).

## Consecuencias
- Una invocación lenta espera hasta `Timeout + 30` s; a cambio, nunca se duplica por el SDK.
- Un `DESCONOCIDO` exige revisar el log (`logs tail -l scheduler`) antes de volver a invocar.
- [T-007](../../backlog/tasks/T-007-lambda-invoke.md) reutiliza `LambdaService` para el ingester y
  las invocaciones genéricas, con las mismas reglas.
- Los demás clientes siguen con `CLIENT_CONFIG`: sus operaciones son lecturas o borrados por clave,
  que se pueden repetir sin efecto.
- Los reenvíos duplicados aguas abajo (una ejecución que reenvía lo que EventBridge ya despachó en
  punto) no los resuelve la CLI; los analiza `../idempotencia-campañas/`.
