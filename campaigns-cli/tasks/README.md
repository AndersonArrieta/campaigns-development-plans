# Tasks — `campaigns-cli`: CLI de pruebas sobre recursos AWS de campañas

Plan de origen: [`../plan-campaigns-cli.md`](../plan-campaigns-cli.md)

Ejecuta las tasks en orden. Cada una deja la CLI ejecutable y las pruebas en verde, así que se puede hacer un commit por task.
El orden va de la base (proyecto uv, `.env`, clientes AWS) a los comandos por recurso y termina con la prueba de punta a punta (`trace run`).

| # | Task | Grupo de comandos | Secciones del plan | Depende de |
|---|---|---|---|---|
| 01 | [Esqueleto del proyecto con uv](01-esqueleto-uv.md) | — | §3, §4, §7 | — |
| 02 | [Settings y carga del `.env`](02-settings-env.md) | `config` | §5, §6 | 01 |
| 03 | [Fábrica AWS, salida y protecciones](03-aws-output-guards.md) | — | §6.1 | 02 |
| 04 | [Comandos `csv`](04-csv-commands.md) | `csv` | §2.1, §6 | 01 |
| 05 | [Comandos `s3`](05-s3-commands.md) | `s3` | §2.1, §6 | 03 |
| 06 | [Comandos `dynamo`](06-dynamo-commands.md) | `dynamo` | §2.1, §6, D-4 | 03 |
| 07 | [Comandos `lambda`](07-lambda-commands.md) | `lambda` | §2.1, §6, D-5 | 03, 05 |
| 08 | [Comandos `logs`](08-logs-commands.md) | `logs` | §2.1, §6 | 03 |
| 09 | [Prueba de punta a punta `trace run`](09-trace-run.md) | `trace` | §2.1, §6, §11 | 04–08 |
| 10 | [Documentación y CI](10-documentacion-ci.md) | — | §7, §11 | 01–09 |

## Convenciones

- **Commit por task:** `feat(campaigns-cli): [T-NN] <resumen de la task>`
- **Comandos de verificación** (desde `campaigns-cli/`):
  - `uv run pytest --cov=campaigns_cli`
  - `uv run ruff check . && uv run ruff format --check .`
  - `uv run mypy src`
- **Separación de capas:** `commands/` solo parsea argumentos y muestra resultados; la lógica va en `services/` y recibe los clientes boto3 inyectados.
- **Sin AWS real en las pruebas:** se usa `moto` y, donde moto no alcanza (invocación de Lambda, Logs Insights), `botocore.stub.Stubber`.
- Las tasks 04, 05, 06 y 08 no dependen entre sí y se pueden hacer en paralelo una vez terminada la 03 (la 04 solo necesita la 01).
- Antes de la T-09 hay que resolver **D-2** (nombres reales de recursos en dev) y **D-4** (GSI por `campaign_id`).
