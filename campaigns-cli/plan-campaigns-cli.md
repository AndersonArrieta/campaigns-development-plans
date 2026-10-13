# Plan — `campaigns-cli`: CLI de pruebas sobre recursos AWS de campañas

- **Carpeta:** `campaigns-cli/`
- **Gestor de proyecto:** [`uv`](https://docs.astral.sh/uv/)
- **Lenguaje:** Python ≥ 3.12
- **Fecha:** 2026-10-13

## 1. Objetivo

Construir una CLI de línea de comandos (`campaigns`) que permita ejecutar, de forma repetible, las pruebas que hoy se hacen a mano sobre los recursos AWS del flujo de campañas:

```
CSV ──(S3)──> ingester_Lambda ──(DynamoDB)──> scheduler_Lambda ──(Kafka)──> platform_campaigns_ms ──(RabbitMQ)──> engine_nlp_ms ──> adapters out
```

La CLI debe:

1. Operar **por comandos y subcomandos** (`campaigns <grupo> <acción> [opciones]`).
2. Leer toda la configuración de entorno (región, perfil, nombres de recursos) desde un archivo **`.env`**, sin valores quemados en el código.
3. Gestionarse completamente con **uv** (dependencias, entorno virtual, ejecución, empaquetado).
4. Producir salidas legibles en consola y, opcionalmente, en JSON para encadenar con otras herramientas.

## 2. Alcance

### 2.1 Dentro del alcance

| Grupo | Recurso AWS | Pruebas |
|---|---|---|
| `config` | — | Mostrar y validar la configuración cargada del `.env`; verificar credenciales (`sts get-caller-identity`). |
| `csv` | — | Generar archivos CSV de campaña válidos (formato de `csv-test.csv`) y validar uno existente. |
| `s3` | Bucket de entrada del ingester | Subir CSV, listar objetos, descargar, borrar archivos de prueba. |
| `lambda` | `ingester_Lambda`, `scheduler_Lambda` | Invocar con un payload (evento S3 / evento programado), ver respuesta y log tail. |
| `dynamo` | Tablas de campañas y de logs del ingester | Buscar por `notification_id`, por `campaign_id`/usuario (scan filtrado), listar por `datetime` (query por hora), revisar las cargas de campañas en la tabla de logs (`logs --follow`), limpiar registros de prueba. |
| `logs` | CloudWatch Logs | Buscar un `notification_id` / `campaign_id` en los log groups de todos los componentes (Logs Insights). |
| `trace` | S3 + Dynamo + Logs | Prueba de punta a punta: subir CSV → esperar ingesta → verificar registros en Dynamo → buscar trazas en logs. |

### 2.2 Fuera del alcance (primera versión)

- Publicar/consumir directamente en Kafka (MSK) o RabbitMQ (Amazon MQ). Se puede añadir como grupo `kafka` / `mq` en una fase posterior (ver §9).
- Crear o destruir infraestructura (eso le corresponde a IaC).
- Ejecutarse en producción: la CLI debe negarse si `CAMPAIGNS_ENV=prod`, salvo comandos de solo lectura (ver §6).

## 3. Stack técnico

| Necesidad | Librería | Motivo |
|---|---|---|
| Framework CLI | `typer` | Subcomandos con type hints, ayuda autogenerada, autocompletado. |
| Salida en consola | `rich` | Tablas, colores, spinners (Typer lo integra). |
| AWS SDK | `boto3` (+ `boto3-stubs[s3,lambda,dynamodb,logs,sts]` en dev) | SDK oficial; stubs para tipado. |
| Configuración / `.env` | `pydantic-settings` (usa `python-dotenv`) | Carga del `.env`, validación de tipos y valores obligatorios con mensajes claros. |
| Pruebas | `pytest`, `moto[s3,dynamodb,lambda,logs]`, `pytest-cov` | Mock de AWS sin tocar la cuenta real. |
| Calidad | `ruff` (lint + format), `mypy` | Estándar del equipo para Python. |

## 4. Estructura del proyecto

```
campaigns-cli/
├── plan-campaigns-cli.md        # este documento
├── pyproject.toml               # gestionado con uv; define el entry point `campaigns`
├── uv.lock
├── .python-version
├── .env.example                 # plantilla versionada (sin secretos)
├── .env                         # NO versionado (en .gitignore)
├── .gitignore
├── README.md
├── src/
│   └── campaigns_cli/
│       ├── __init__.py
│       ├── main.py              # app Typer raíz; registra los subgrupos
│       ├── settings.py          # clase Settings (pydantic-settings)
│       ├── aws.py               # fábrica de sesiones/clientes boto3 a partir de Settings
│       ├── output.py            # helpers de salida: tabla rich / JSON
│       ├── guards.py            # protecciones de entorno (bloqueo prod, confirmaciones)
│       ├── commands/
│       │   ├── config_cmd.py
│       │   ├── csv_cmd.py
│       │   ├── s3_cmd.py
│       │   ├── lambda_cmd.py
│       │   ├── dynamo_cmd.py
│       │   ├── logs_cmd.py
│       │   └── trace_cmd.py
│       └── services/            # lógica sin dependencias de Typer (testeable)
│           ├── csv_service.py
│           ├── s3_service.py
│           ├── lambda_service.py
│           ├── dynamo_service.py
│           ├── logs_service.py
│           └── trace_service.py
└── tests/
    ├── conftest.py              # fixtures moto + Settings de prueba
    ├── test_settings.py
    ├── test_csv_service.py
    ├── test_s3_service.py
    ├── test_dynamo_service.py
    ├── test_lambda_service.py
    ├── test_logs_service.py
    └── test_cli.py              # typer.testing.CliRunner
```

**Regla:** `commands/` solo parsea argumentos y muestra resultados; toda la lógica vive en `services/` y recibe los clientes boto3 inyectados, para poder probarla con moto.

## 5. Configuración por `.env`

### 5.1 Variables

`.env.example` (versionado):

```dotenv
# --- Entorno ---
CAMPAIGNS_ENV=dev                      # dev | qa | prod
AWS_REGION=us-east-1

# --- Credenciales AWS (prioridad sobre AWS_PROFILE) ---
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=                     # solo credenciales temporales
AWS_PROFILE=                           # alternativa: perfil / SSO

# --- Recursos ---
CAMPAIGNS_INPUT_BUCKET=
CAMPAIGNS_INPUT_PREFIX=campaigns/input/
CAMPAIGNS_TABLE_NAME=
CAMPAIGNS_TABLE_CAMPAIGN_INDEX=        # GSI por campaign_id (hoy no existe => scan filtrado)
CAMPAIGNS_LOGS_TABLE_NAME=             # tabla de logs de ejecución del ingester
INGESTER_LAMBDA_NAME=
SCHEDULER_LAMBDA_NAME=

# --- Logs (separados por coma) ---
CAMPAIGNS_LOG_GROUPS=/aws/lambda/ingester,/aws/lambda/scheduler,/ecs/platform-campaigns-ms,/ecs/engine-nlp-ms

# --- Comportamiento ---
CLI_OUTPUT=table                       # table | json
CLI_WAIT_TIMEOUT_SECONDS=120
CLI_POLL_INTERVAL_SECONDS=5
CLI_TEST_APP_ID=others-test            # app_id usado para datos de prueba (y para limpieza)
```

> Los nombres reales de bucket, tabla, lambdas y log groups por ambiente deben confirmarse con el equipo (ver D-2).

### 5.2 Reglas de carga

- `Settings` (pydantic-settings) lee, en este orden de prioridad: **variables de entorno del proceso > archivo `.env`** > valores por defecto.
- Opción global `--env-file PATH` para usar otro archivo (ej. `.env.qa`) sin editar el principal.
- Las variables obligatorias (bucket, tabla, nombres de lambdas) se validan **solo cuando el comando las necesita**, para que `campaigns config show` o `campaigns csv generate` funcionen aunque falten.
- Las credenciales AWS se pasan por el `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y, si son temporales, `AWS_SESSION_TOKEN`) y tienen prioridad sobre `AWS_PROFILE`. Si no están, se usa `AWS_PROFILE` o la cadena estándar de boto3.
- Las credenciales se manejan como `SecretStr`: no aparecen en `repr`, tracebacks ni mensajes de validación, y `config show` las muestra enmascaradas. `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` deben ir juntas.
- El `.env` nunca se versiona; `.env.example` va sin valores.
- `.env` y `.env.*` (excepto `.env.example`) van en `.gitignore`.

## 6. Diseño de comandos

Opciones globales (en el callback raíz): `--env-file`, `--output table|json`, `--verbose`, `--yes` (omitir confirmaciones).

```text
campaigns config show                         # configuración efectiva (enmascara valores sensibles)
campaigns config check                        # valida .env + sts get-caller-identity + existencia de recursos

campaigns csv generate --users 573232540390,573... --canal WhatsApp \
                       --fecha 13/10/2026 --hora 10 --nodo N-03-99-10 \
                       [--app-id others-test] [--parametros k=v] -o campaign.csv
campaigns csv validate campaign.csv           # columnas, separador ';', formato dd/mm/yyyy, horas, días

campaigns s3 upload campaign.csv [--key ...]  # sube al bucket/prefijo del ingester
campaigns s3 ls [--prefix ...]
campaigns s3 get <key> [-o archivo]
campaigns s3 rm <key>                         # pide confirmación

campaigns lambda invoke ingester --s3-key <key>   # construye un evento S3 sintético
campaigns lambda invoke scheduler [--payload evento.json]
campaigns lambda invoke <nombre> --payload file.json [--tail]  # genérico; --tail muestra el LogResult

campaigns dynamo get --notification-id <id> [--datetime ...]
campaigns dynamo find --campaign-id <id>
campaigns dynamo list --from "2026-10-13 00:00:00" --to "2026-10-13 23:59:59" [--app-id ...]
campaigns dynamo purge --campaign-id <id>     # borra registros de prueba; pide confirmación

campaigns logs search --id <notification_id|campaign_id> [--since 1h] [--group ...]

campaigns trace run campaign.csv [--timeout 120]
    # 1. valida CSV  2. sube a S3  3. espera registros en Dynamo por app_id/fecha
    # 4. muestra notification_id y campaign_id  5. busca ambos en CloudWatch por componente
    # 6. reporta tabla OK/FALLA por etapa; exit code ≠ 0 si alguna falla
```

### 6.1 Convenciones

- **Códigos de salida:** `0` OK, `1` prueba fallida, `2` error de uso/configuración, `3` error de AWS (credenciales, permisos, recurso inexistente).
- **Salida JSON** (`--output json`) estable, para usarla en scripts o pipelines.
- **Protecciones (`guards.py`):**
  - Si `CAMPAIGNS_ENV=prod`, solo se permiten comandos de lectura (`config`, `dynamo get/find/list`, `logs search`, `s3 ls`).
  - Los comandos destructivos (`s3 rm`, `dynamo purge`) piden confirmación salvo `--yes`, y `purge` solo borra registros cuyo `app_id` sea `CLI_TEST_APP_ID`.
- Errores de boto3 (`ClientError`, `NoCredentialsError`) se traducen a mensajes cortos con sugerencia (ej. "revisa AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN en el .env").

## 7. Uso de uv

```bash
# Inicialización (una sola vez)
uv init --package campaigns-cli          # layout src/ con entry point
uv add typer rich boto3 pydantic-settings
uv add --dev pytest pytest-cov "moto[s3,dynamodb,lambda,logs]" ruff mypy "boto3-stubs[s3,lambda,dynamodb,logs,sts]"

# Día a día
uv sync                                  # crea .venv e instala según uv.lock
uv run campaigns --help                  # ejecutar la CLI
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check . && uv run mypy src

# Instalación global opcional
uv tool install --editable .             # deja `campaigns` disponible en el PATH
```

`pyproject.toml` declara el entry point:

```toml
[project.scripts]
campaigns = "campaigns_cli.main:app"
```

## 8. Fases y tasks

| # | Task | Entregable | Depende de |
|---|---|---|---|
| 01 | Esqueleto con uv | `uv init --package`, dependencias, `.gitignore`, `.env.example`, `campaigns --help` funcionando | — |
| 02 | Settings y `.env` | `settings.py`, opción `--env-file`, `config show` / `config check` | 01 |
| 03 | Fábrica AWS + salida + guards | `aws.py`, `output.py`, `guards.py`, manejo de errores y exit codes | 02 |
| 04 | Comandos `csv` | `generate` y `validate` (sin AWS) | 01 |
| 05 | Comandos `s3` | `upload`, `ls`, `get`, `rm` + tests con moto | 03 |
| 06 | Comandos `dynamo` | `get`, `find`, `list`, `purge` + tests con moto | 03 |
| 07 | Comandos `lambda` | `invoke` genérico, ingester (evento S3 sintético), scheduler, `--tail` | 03 |
| 08 | Comandos `logs` | `search` con Logs Insights sobre varios log groups | 03 |
| 09 | Comando `trace run` | Orquestación E2E con espera/polling y reporte por etapa | 04–08 |
| 10 | Documentación y CI | `README.md` (instalación, `.env`, ejemplos), job de lint + tests | 01–09 |

**Convenciones:** commit por task (`feat(campaigns-cli): <resumen>`); cada task deja `uv run pytest` y `uv run ruff check .` en verde.

## 9. Evolución posible (fase 2)

- Grupo `kafka`: publicar un evento al topic del scheduler (MSK con IAM auth, `confluent-kafka` o `aiokafka`) para probar `platform_campaigns_ms` aislado.
- Grupo `mq`: inspeccionar colas de RabbitMQ (Amazon MQ) vía API de administración.
- `trace run` extendido hasta adapters out, validando `CorrelationId = notification_id` en cada componente (complementa la HU 7938050).
- Perfiles de prueba guardados (`scenarios/*.yaml`) para ejecutar baterías de pruebas con un solo comando.

## 10. Decisiones abiertas

| ID | Decisión | Propuesta |
|---|---|---|
| D-1 | Framework CLI | **Typer** (alternativa: Click puro). |
| D-2 | Nombres reales de recursos por ambiente (bucket, prefijo, tabla, GSI, lambdas, log groups) | Parcial (T-06): patrones de bucket, tablas de campañas y logs, y scheduler tomados de `Platform_test` (ver `.env.example`). Faltan ingester y log groups. |
| D-3 | Autenticación AWS | ✅ Decidido (2026-10-13): credenciales en el `.env` (no versionado), con `AWS_PROFILE` como alternativa. |
| D-4 | ¿Existe GSI por `campaign_id` en la tabla de campañas? | ✅ Resuelto (T-06): **no existe**. `dynamo find` usa scan filtrado con aviso. |
| D-5 | ¿Invocar el ingester directamente o solo vía subida a S3? | Soportar ambos: `s3 upload` (flujo real) y `lambda invoke ingester` (aislado). |
| D-6 | Ubicación del código | Repo propio o carpeta `campaigns-cli/` dentro de este repo de planes. |

## 11. Criterios de aceptación

1. `uv sync && uv run campaigns --help` funciona en una máquina limpia con solo `uv` instalado.
2. Toda la configuración de entorno sale del `.env` (o `--env-file`); no hay nombres de recursos quemados en el código.
3. `campaigns config check` detecta variables faltantes, credenciales inválidas y recursos inexistentes con mensajes claros.
4. `campaigns trace run csv-test.csv` en dev reporta, por etapa, si el CSV se subió, si se crearon los registros en Dynamo y en qué componentes aparecen sus `notification_id` / `campaign_id` en los logs.
5. Los comandos destructivos están bloqueados en prod y piden confirmación en los demás ambientes.
6. Cobertura de pruebas ≥ 80 % en `services/`, usando moto (sin llamadas reales a AWS en la suite).
