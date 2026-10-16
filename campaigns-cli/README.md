# campaigns-cli

CLI de pruebas sobre los recursos AWS del flujo de campañas.

Documentación técnica: [`docs/`](docs/README.md) · Backlog: [`backlog/`](backlog/README.md) (vault de Obsidian, ejecutable por un agente)

## Inicio rápido

### 1. Preparar el entorno (una sola vez)

```bash
source ~/.local/bin/env                                  # uv en el PATH
export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/campaigns-cli  # .venv fuera de OneDrive
uv sync
```

> **WSL + OneDrive:** el `.venv` dentro de `/mnt/c` hace todo muy lento (pruebas ~220 s → ~5 s).
> Agrega las dos primeras líneas a `~/.bashrc` para no repetirlas en cada terminal.

### 2. Crear el `.env`

Desde la carpeta `campaigns-cli/`:

```bash
cp .env.example .env
```

El `.env` no se versiona (está en `.gitignore`). Para los comandos `dynamo` bastan estas variables; cambia `dev` por el ambiente que corresponda:

```dotenv
CAMPAIGNS_ENV=dev
AWS_REGION=us-east-1

# Credenciales de la cuenta donde están las tablas
AWS_ACCESS_KEY_ID=AKIA... o ASIA...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...          # solo si son temporales (las que empiezan por ASIA)

# Tablas
CAMPAIGNS_TABLE_NAME=nu0284001-artemis-chatbots-platform-dev-scheduled-campaigns
CAMPAIGNS_LOGS_TABLE_NAME=nu0284001-artemis-chatbots-platform-dev-scheduled-campaigns-logs
```

- Sin comillas.
- `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` van siempre juntas; si falta una, la CLI no arranca.
- Las credenciales temporales vencen en pocas horas: si aparece "Sin credenciales" o "vencidas", actualízalas.
- Prioridad de carga: variables de entorno del proceso > `.env` > valores por defecto.
- Para otro ambiente sin editar el `.env`: `uv run campaigns --env-file .env.qa ...`.

### 3. Verificar la configuración

```bash
uv run campaigns config show     # configuración cargada (las credenciales salen ocultas)
uv run campaigns config check    # identidad AWS y existencia de los recursos
```

En `config check` las dos tablas deben salir **OK**. El resto (bucket, lambdas, log groups) saldrá como `FALTA CONFIG` y el comando terminará con código 1; para probar `dynamo` no importa. Si una tabla sale **SIN PERMISO**, al usuario de las llaves le falta acceso.

Permisos mínimos (solo lectura) para `config` y `dynamo`:

- `sts:GetCallerIdentity`
- `dynamodb:DescribeTable`, `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan` sobre las dos tablas

## Comandos `dynamo`

| Tabla | PK | SK | Contenido |
|---|---|---|---|
| Campañas | `datetime` (`YYYY-MM-DD HH:00:00`, hora Colombia) | `notification_id` | Una notificación programada por usuario y fecha/hora: `campaign_id`, `app_id`, `channel`, `user`, `notification_node`, `retries`, `context`, `expiration_date` |
| Logs | `app_id` | `datetime` (con microsegundos) | Una fila por CSV procesado por el ingester: estado, estadísticas, `campaign_id` y archivo |

Un recorrido típico: ver las cargas recientes y seguir el rastro de una de ellas.

```bash
uv run campaigns dynamo logs --since 7d                     # últimas cargas de CSV (todas las apps)
uv run campaigns dynamo logs --app-id <app_id> --details    # errores de validación de una app
uv run campaigns dynamo find --campaign-id <id de la carga> # notificaciones creadas por esa carga
uv run campaigns dynamo list --date 2026-10-13              # lo programado ese día (hora Colombia)
uv run campaigns dynamo list --date 2026-10-13 --hour 10    # lo que el scheduler enviará a esa hora
uv run campaigns dynamo get --notification-id <id> --datetime "2026-10-13 10"
uv run campaigns dynamo logs -f                             # sigue las cargas nuevas (Ctrl+C para salir)
uv run campaigns dynamo history --since 2h                  # cada carga con sus filas y reprogramaciones
uv run campaigns dynamo campaign --campaign-id <id>         # línea de tiempo de cada notification_id del CSV
uv run campaigns dynamo get --notification-id <id>          # todas las filas (original y reprogramadas)
uv run campaigns --output json dynamo dump > evidencias/dump.json   # todas las filas de las dos tablas
```

- `--output json` (antes del subcomando) devuelve JSON limpio en stdout, para usarlo con `jq`.
- Una notificación reprogramada por `platform_campaigns_ms` tiene varias filas con el mismo `notification_id`: `history`, `campaign` y `get` marcan cada una como `ORIGINAL`, `FUERA_DE_HORARIO` o `REINTENTO`, y como `PENDIENTE`, `EN_CURSO` o `PASADA` según la hora Colombia actual.
- `find`, `get` sin `--datetime`, `history`, `campaign`, `dump` y `logs` sin `--app-id` hacen **scan** (recorren la tabla) y lo avisan; en tablas grandes son más lentos y costosos.
- `list` hace un query por cada hora del rango (máximo 31 días), sin scan.
- `logs --since` usa UTC (se asume que la Lambda guarda la fecha en UTC). Si una carga reciente no aparece con `--since 2h`, prueba con `--since 1d` y revisa la diferencia de horas.

### Limpiar datos de prueba: `dynamo purge`

```bash
uv run campaigns dynamo purge --campaign-id <id de la carga>          # pide confirmación
uv run campaigns --yes dynamo purge --campaign-id <id de la carga>    # sin preguntar
```

Borra de la tabla de campañas los registros de ese `campaign_id` cuyo `app_id` es `CLI_TEST_APP_ID`
(los de otro `app_id` se omiten y se informan). No toca la tabla de logs. Está bloqueado con
`CAMPAIGNS_ENV=prod` y necesita además el permiso `dynamodb:BatchWriteItem` sobre la tabla de campañas.

### Vaciar las tablas antes de una prueba: `dynamo clean`

```bash
uv run campaigns dynamo clean --dry-run                    # qué se borraría, sin borrar
uv run campaigns dynamo clean                              # vacía las dos tablas (pide confirmación)
uv run campaigns dynamo clean --table logs                 # solo la tabla de logs
uv run campaigns --yes dynamo clean --campaign-id <id>     # solo lo que dejó ese CSV, sin preguntar
```

Las tablas de dev son de uso exclusivo de las pruebas, así que `clean` sin `--campaign-id` borra
**todas** las filas, de todos los `app_id` ([ADR-0011](docs/adr/0011-vaciado-de-tablas-en-dev.md)).
Antes de borrar muestra cuántas filas hay por tabla y `app_id`, cuántas son reprogramaciones y cuántas
están `PENDIENTE` o `EN_CURSO`; al final verifica con un scan y sale con 1 si quedó alguna. Bloqueado
en prod; necesita `dynamodb:BatchWriteItem` sobre las dos tablas.

## Comandos `logs` (CloudWatch, solo lectura)

Requieren en el `.env` los nombres de las lambdas (los log groups se derivan como `/aws/lambda/<nombre>`):

```dotenv
INGESTER_LAMBDA_NAME=nu0284001-artemis-plc-dev-campaigns-ingester-lambda
SCHEDULER_LAMBDA_NAME=nu0284001-artemis-plc-dev-campaigns-scheduler-lambda
```

Permisos: `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:StartQuery`, `logs:GetQueryResults` y `logs:StopQuery`.

```bash
uv run campaigns logs groups                                   # log groups de artemis (para descubrir nombres)
uv run campaigns logs tail -l scheduler                        # últimos 15 min del scheduler
uv run campaigns logs tail -l ingester --since 2h --filter "Campaign"
uv run campaigns logs tail -l scheduler -f                     # seguir en vivo (Ctrl+C)
uv run campaigns logs search --id <notification_id>            # en qué lambda aparece (últimas 24 h)
uv run campaigns logs search --id <campaign_id> -l ingester --from "2026-10-13 08:00"
```

- Las horas (`--from`, `--to` y las que se muestran) son **hora Colombia**.
- `search` usa Logs Insights: busca el texto literal (mínimo 6 caracteres), muestra un resumen por componente y sale con código 1 si no hay coincidencias.
- Otros log groups (ej. `platform_campaigns_ms`): `--group <log group>` o `CAMPAIGNS_LOG_GROUPS` en el `.env`.

### Log completo de una lambda en un rango horario

`logs tail` con `--from` y `--to`. Por defecto solo muestra los **últimos 100 eventos** del rango; sube `-n` para verlo completo:

```bash
uv run campaigns logs tail -l scheduler --from "2026-10-13 08:00" --to "2026-10-13 10:00" -n 100000
```

- `-l ingester` o `-l scheduler` elige la lambda (o `-g <log group>` para cualquier otro).
- Formatos de hora: `YYYY-MM-DD HH`, `YYYY-MM-DD HH:MM` o `YYYY-MM-DD HH:MM:SS`.
- Muestra cada evento completo con su hora, en orden cronológico.
- Si el rango tiene más eventos que `-n`, avisa que se cortó y conserva los más recientes.

Guardarlo en un archivo:

```bash
# Texto, como se ve en pantalla
uv run campaigns logs tail -l scheduler --from "2026-10-13 08:00" --to "2026-10-13 10:00" -n 100000 > scheduler.log

# JSON (hora, log stream y mensaje completo por evento; útil con jq)
uv run campaigns --output json logs tail -l scheduler --from "2026-10-13 08:00" --to "2026-10-13 10:00" -n 100000 > scheduler.json
```

`--output json` va **antes** de `logs` porque es una opción global.

Variantes:

```bash
# Solo las líneas que contienen un texto en ese rango
uv run campaigns logs tail -l ingester --from "2026-10-13 08:00" --to "2026-10-13 10:00" --filter "Campaign" -n 100000

# Una ejecución concreta del scheduler (corre cada hora): basta un rango corto
uv run campaigns logs tail -l scheduler --from "2026-10-13 09:00" --to "2026-10-13 09:05" -n 100000
```

La CLI trae todos los eventos del rango antes de mostrarlos: en rangos de muchas horas con mucho log puede tardar. Si es así, acota el rango o usa `--filter`.

## Comandos `scheduler` (invocar `scheduler_Lambda` a demanda)

En lugar de esperar a la hora en punto, despacha la partición de la hora en curso (hora Colombia).
Requieren `SCHEDULER_LAMBDA_NAME` y, para `run`, `CAMPAIGNS_TABLE_NAME`, con credenciales que
tengan `lambda:InvokeFunction` (las de solo lectura no alcanzan):

```bash
uv run campaigns scheduler health                 # prueba Kafka; no despacha nada
uv run campaigns scheduler run                    # vista previa por app_id, confirma e invoca una vez
uv run campaigns scheduler run --tail --yes       # sin confirmación y con los últimos 4 KB del log
```

- Flujo de prueba: CSV con la hora actual → `scheduler run`.
- **No es idempotente:** reenvía a Kafka **todas** las filas de la hora, también las que EventBridge
  ya despachó y las de otros equipos (la vista previa lo avisa).
- Nunca reintenta algo que pudo haber ejecutado la Lambda: si no hay respuesta clara, el resultado es
  `DESCONOCIDO` (exit 3); revisa `logs tail -l scheduler` antes de volver a invocar.
- Bloqueado con `CAMPAIGNS_ENV=prod`.

## Comandos `channel` (fake channel, solo lectura)

Verifican que el mensaje de una campaña llegó al usuario, como la prueba E2E de `Platform_test`.
Requieren en el `.env` (valores del pipeline de `Platform_test`; el secreto nunca se versiona):

```dotenv
COGNITO_TOKEN_URL=https://chatbots-artemis-dev.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=...
COGNITO_CLIENT_SECRET=...
FAKE_CHANNEL_BASE_URL=https://informacion-ext-dev.apps.ambientesbc.com/artemis/platform/fake-channel/v1
FAKE_CHANNEL_VERIFY_SSL=false   # solo si el certificado del ambiente no es de confianza
```

```bash
uv run campaigns channel messages --canal whatsapp --user 574141179337
uv run campaigns channel verify --canal whatsapp --user 574141179337 --text Campaig_e2e_test_delivered_successfully
uv run campaigns channel messages --canal teams --user 27060555-ecc0-4aad-85b6-9a663cd04331
```

- En Teams, `--user` es el `recipient.id` (UUID), no el email del CSV. `--canal` acepta también `msteams`.
- `verify` reintenta 5 veces cada 10 s (`--attempts`, `--interval`) y sale con 1 si el mensaje no llegó.
- El fake channel no borra mensajes: uno de una corrida anterior con el mismo texto cuenta como entregado.

## Comandos `pods` (logs de campaigns y engine en EKS, solo lectura)

Reemplazan `aws eks update-kubeconfig ...` + `kubectl logs -f -l app=platform-campaigns-others-v2 --tail 1000`,
con las mismas credenciales del `.env` y sin `kubectl` instalado:

```dotenv
EKS_CLUSTER_NAME=eks-informacion-dev
EKS_NAMESPACE=artemis-dev
# CAMPAIGNS_POD_SELECTOR=app=platform-campaigns-others-v2         (valor por defecto)
# ENGINE_POD_SELECTOR=app=platform-engine-nlp-others-campaigns    (valor por defecto)
```

```bash
uv run campaigns pods ls                                   # pods del microservicio
uv run campaigns pods logs --tail 1000 -f                  # como el kubectl logs -f de siempre
uv run campaigns pods logs -k engine --tail 200             # el engine (-k campaigns|engine|all)
uv run campaigns pods logs --notification-id <id> -C 2       # rastro de una notificación en campaigns y engine
uv run campaigns pods scan <id> -C 2                         # lo mismo, primero campaigns y luego engine
uv run campaigns pods scan <id> -k engine -k campaigns       # otro orden, o un solo componente con -k
uv run campaigns --output json pods logs --since 30m > campaigns-ms.json
```

- Horas en hora Colombia; cada línea lleva `[componente]` y el nombre del pod.
- `--notification-id` busca en los dos componentes (últimas 24 h), resume dónde apareció y sale con 1 si no está; `-C 2` muestra las líneas vecinas (en el engine el id va dentro del JSON y las líneas relacionadas no lo llevan).
- `pods scan` hace la misma búsqueda microservicio por microservicio en el orden de `-k`: un bloque por componente con encabezado, líneas y resumen, en vez de mezclar las líneas de los dos.
- Permisos: `eks:DescribeCluster` y acceso RBAC a `pods` y `pods/log` en el namespace.

## Notas

- Ejecuta los comandos desde `campaigns-cli/`: el `.env` se busca en la carpeta actual. Desde otra carpeta usa `--env-file ruta/al/.env`.
- Códigos de salida: `0` OK, `1` prueba fallida, `2` error de uso o configuración, `3` error de AWS o de un servicio externo (Cognito, fake channel).
- `--verbose` muestra el traceback completo de un error.

## Desarrollo

```bash
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```
