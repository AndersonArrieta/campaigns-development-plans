# campaigns-cli

CLI de pruebas sobre los recursos AWS del flujo de campañas.

Plan: [`plan-campaigns-cli.md`](plan-campaigns-cli.md) · Tasks: [`tasks/`](tasks/README.md)

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

## Comandos `dynamo` (solo lectura)

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
```

- `--output json` (antes del subcomando) devuelve JSON limpio en stdout, para usarlo con `jq`.
- `find`, `get` sin `--datetime` y `logs` sin `--app-id` hacen **scan** (recorren la tabla) y lo avisan; en tablas grandes son más lentos y costosos.
- `list` hace un query por cada hora del rango (máximo 31 días), sin scan.
- `logs --since` usa UTC (se asume que la Lambda guarda la fecha en UTC). Si una carga reciente no aparece con `--since 2h`, prueba con `--since 1d` y revisa la diferencia de horas.

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

## Notas

- Ejecuta los comandos desde `campaigns-cli/`: el `.env` se busca en la carpeta actual. Desde otra carpeta usa `--env-file ruta/al/.env`.
- Códigos de salida: `0` OK, `1` prueba fallida, `2` error de uso o configuración, `3` error de AWS.
- `--verbose` muestra el traceback completo de un error.

## Desarrollo

```bash
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```
