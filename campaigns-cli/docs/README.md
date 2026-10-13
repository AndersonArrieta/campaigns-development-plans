# Documentación técnica — `campaigns-cli`

CLI de línea de comandos (`campaigns`) para ejecutar de forma repetible las pruebas que hoy
se hacen a mano sobre los recursos AWS del flujo de campañas.

Esta carpeta describe **cómo funciona la CLI hoy**. Lo que falta por construir y el orden de
trabajo están en el **[backlog](../backlog/README.md)** (vault de Obsidian, ejecutado por un
agente tarjeta a tarjeta). La guía rápida de uso está en el [README del proyecto](../README.md).

| Documento | Contenido |
|---|---|
| [Arquitectura](arquitectura.md) | Capas, módulos, ciclo de una invocación, errores y salida. |
| [Configuración](configuracion.md) | Variables del `.env`, credenciales, nombres de recursos por ambiente y permisos IAM. |
| [Comandos](comandos.md) | Referencia de cada grupo y subcomando, implementados y planeados. |
| [Recursos AWS](recursos-aws.md) | Esquemas de las tablas DynamoDB, log groups, bucket y cómo los consulta la CLI. |
| [Desarrollo](desarrollo.md) | Entorno con uv, pruebas, calidad, cómo agregar un grupo y cómo trabajar con el backlog. |
| [Decisiones (ADR)](adr/README.md) | Decisiones de arquitectura y su estado. |

## Contexto: el flujo de campañas

```
CSV ──(S3)──> ingester_Lambda ──(DynamoDB)──> scheduler_Lambda ──(Kafka)──> platform_campaigns_ms ──(RabbitMQ)──> engine_nlp_ms ──> adapters out
```

1. Un CSV de campaña llega al bucket de entrada y dispara `ingester_Lambda`.
2. El ingester valida el archivo, genera un `campaign_id` por archivo y un `notification_id`
   por usuario y fecha/hora, y escribe una fila por notificación en la **tabla de campañas**
   y una fila por archivo en la **tabla de logs**.
3. `scheduler_Lambda` corre cada hora, lee la partición de esa hora y publica en Kafka.
4. `platform_campaigns_ms`, `engine_nlp_ms` y los adapters entregan el mensaje. En dev y qa los
   adapters entregan a un **fake channel** que guarda los mensajes por usuario y se consulta por
   HTTP con un token de Cognito ([comandos](comandos.md), grupo `channel`).

La CLI cubre los pasos 1–3 (S3, Lambdas, DynamoDB y CloudWatch Logs) y la entrega final en el fake channel (grupo `channel`). Los logs de `platform_campaigns_ms`
y `engine_nlp_ms` se leen de sus pods en EKS (grupo `pods`). Publicar o consumir
directamente en Kafka o RabbitMQ y crear infraestructura quedan fuera del alcance.

## Objetivos de diseño

- **Comandos y subcomandos:** `campaigns <grupo> <acción> [opciones]`.
- **Configuración solo por `.env`:** ningún nombre de recurso quemado en el código
  ([configuración](configuracion.md)).
- **Gestionada con uv:** dependencias, entorno, ejecución y empaquetado
  ([ADR-0001](adr/0001-typer-y-uv.md)).
- **Salida para personas y para scripts:** tabla en consola o JSON estable con `--output json`.
- **Segura por defecto:** en prod solo lectura; lo destructivo pide confirmación
  ([arquitectura § protecciones](arquitectura.md#protecciones)).

## Estado por grupo de comandos

| Grupo | Recurso | Estado | Tarjetas |
|---|---|---|---|
| `config` | — / STS | ✅ implementado | [T-002](../backlog/tasks/T-002-settings-env.md), [T-003](../backlog/tasks/T-003-aws-output-guards.md) |
| `dynamo` | DynamoDB | ✅ lectura · ⏳ `purge` | [T-006](../backlog/tasks/T-006-dynamo-lectura.md), [T-012](../backlog/tasks/T-012-dynamo-purge.md) |
| `logs` | CloudWatch Logs | ✅ implementado | [T-008](../backlog/tasks/T-008-logs-cloudwatch.md) |
| `csv` | — | ⏳ pendiente | [T-004](../backlog/tasks/T-004-csv-generate-validate.md) |
| `s3` | S3 | ⏳ pendiente | [T-005](../backlog/tasks/T-005-s3-commands.md) |
| `lambda` | Lambda | ⏳ pendiente | [T-007](../backlog/tasks/T-007-lambda-invoke.md) |
| `trace` | S3 + DynamoDB + Logs | ⏳ pendiente | [T-009](../backlog/tasks/T-009-trace-run.md), [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md), [T-016](../backlog/tasks/T-016-trace-entrega-canal.md) |
| `pods` | EKS (API de Kubernetes): campaigns y engine | ✅ implementado | [T-017](../backlog/tasks/T-017-pods-logs-eks.md), [T-018](../backlog/tasks/T-018-pods-engine-notification-id.md) |
| `channel` | Cognito + fake channel (HTTP) | ✅ implementado | [T-015](../backlog/tasks/T-015-fake-channel-messages.md), [T-016](../backlog/tasks/T-016-trace-entrega-canal.md) (en `trace`) |

Validación contra la cuenta real de dev: [T-011](../backlog/tasks/T-011-validar-lectura-dev.md).
CI: [T-014](../backlog/tasks/T-014-ci-github-actions.md). Documentación de uso final: [T-010](../backlog/tasks/T-010-documentacion.md).

## Criterios de aceptación del proyecto

| # | Criterio | Estado | Dónde se cierra |
|---|---|---|---|
| 1 | `uv sync && uv run campaigns --help` funciona en una máquina limpia con solo `uv`. | ✅ | [T-001](../backlog/tasks/T-001-esqueleto-uv.md) |
| 2 | Toda la configuración sale del `.env` (o `--env-file`); no hay nombres de recursos quemados en el código. | ✅ salvo el prefijo por defecto de `logs groups` (`/aws/lambda/nu0284001-artemis`) | [T-002](../backlog/tasks/T-002-settings-env.md) |
| 3 | `config check` detecta variables faltantes, credenciales inválidas y recursos inexistentes con mensajes claros. | ✅ con moto · ⏳ en dev | [T-003](../backlog/tasks/T-003-aws-output-guards.md), [T-011](../backlog/tasks/T-011-validar-lectura-dev.md) |
| 4 | `trace run csv-test.csv` en dev reporta por etapa si el CSV se subió, si se crearon los registros y en qué componentes aparecen sus IDs. | ⏳ | [T-009](../backlog/tasks/T-009-trace-run.md), [T-013](../backlog/tasks/T-013-trace-aguas-abajo.md) |
| 5 | Los comandos destructivos están bloqueados en prod y piden confirmación en los demás ambientes. | ⏳ (guards listos, faltan los comandos) | [T-005](../backlog/tasks/T-005-s3-commands.md), [T-012](../backlog/tasks/T-012-dynamo-purge.md) |
| 6 | Cobertura ≥ 80 % en `services/` con moto, sin llamadas reales a AWS en la suite. | ✅ 96 % hoy · ⏳ umbral en CI | [T-014](../backlog/tasks/T-014-ci-github-actions.md) |
