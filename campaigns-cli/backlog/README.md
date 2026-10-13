# Backlog — `campaigns-cli` (modo agente)

Backlog de la CLI de pruebas sobre los recursos AWS del flujo de campañas, como **vault de
Obsidian versionado con git**. Lo ejecuta un agente IA tarjeta a tarjeta; el orden lo dicta el
**grafo de dependencias + prioridad**, no un calendario. Sustituye a la antigua carpeta
`campaigns-cli/tasks/` (T-01…T-10) y al plan `plan-campaigns-cli.md` (ver historial de git).
La documentación técnica de cómo funciona la CLI hoy está en [`../docs/`](../docs/README.md).

## Modelo

- **El frontmatter es la única fuente de verdad.** Todas las vistas (tablero, ready queue,
  roadmap, épicas) se generan con Dataview; no hay listas mantenidas a mano.
- **La ready queue es el driver:** [[ready-queue]] muestra las tarjetas cuyas `depends_on`
  están todas en `done`, ordenadas por prioridad.
- **Añadir trabajo = crear un `.md`** en `tasks/` o `bugs/` a partir de `_templates/`, con el
  siguiente id libre.
- **Backlog vs. documentación:** el backlog dice *qué cambiar*; cómo funciona hoy la CLI está
  en [`../docs/`](../docs/README.md) (arquitectura, configuración, comandos, recursos AWS,
  desarrollo). Una tarjeta que cambia el comportamiento actualiza `docs/` en la misma tarjeta.
- **Decisiones → ADR:** si una tarjeta toma o cambia una decisión de arquitectura, escribe un
  ADR en [`../docs/adr/`](../docs/adr/README.md). Un ADR `accepted` no se edita: se reemplaza.

### Bucle de ejecución del agente
```
mientras existan tareas no-done:
    ready = tareas con status ∈ {backlog, todo} y todas sus depends_on = done
    siguiente = ready ordenada por priority (P0 → P3)
    → poner status: doing
    → implementar (registrar el grupo en main.py si es nuevo; no hay build ni deploy)
    → correr el bloque "## Verificación" de la tarjeta (pytest, ruff, mypy + comandos propios)
    → si pasa: status: done ; si no: status: blocked + nota
```
El agente puede calcularlo leyendo el frontmatter de `tasks/` y `bugs/`; **no necesita
Obsidian** (Obsidian es solo la capa visual para humanos).

Para ejecutar una tarjeta con un LLM: usa [`_prompts/execute-task.md`](_prompts/execute-task.md)
como **mensaje de sistema** y el id de la tarjeta (`T-004`) como **mensaje de usuario**.

### Estructura
```
backlog/
├── _templates/
│   ├── task.md             # plantilla de tarea/funcionalidad (T-0NN)
│   └── bug.md              # plantilla de bug (B-0NN)
├── _prompts/
│   └── execute-task.md     # system prompt: ejecuta UNA tarjeta con un LLM (le pasas el id)
├── tasks/                  # T-0NN-<slug>.md — tareas y funcionalidades
├── bugs/                   # B-0NN-<slug>.md — bugs
├── epics/                  # E-<tema>.md — épicas TEMÁTICAS (por capacidad) con su Dataview
├── dashboards/
│   ├── ready-queue.md      # ⭐ cola del agente: desbloqueadas + bloqueadas + en curso
│   ├── board.md            # Kanban por status
│   ├── bugs.md             # 🐞 bugs abiertos/cerrados
│   └── roadmap.md          # progreso por epic
└── README.md
```

### Campos del frontmatter
| Campo | Valores | Uso |
|---|---|---|
| `id` | `T-0NN` (tarea) · `B-0NN` (bug) · `E-<tema>` (épica) | identificador estable, nunca se reutiliza |
| `aliases` | `[<id>]` | autocompletado por id en Obsidian |
| `title` | string entre comillas | título humano |
| `status` | `backlog` → `todo` → `doing` → `blocked` → `done` | estado |
| `priority` | `P0` `P1` `P2` `P3` | desempate en la ready queue |
| `epic` | `E-<tema>` | agrupación por capacidad |
| `estimate` | `S` `M` `L` | tamaño |
| `depends_on` | `[T-0NN, ...]` | **precedencia — define el orden real de ejecución** |
| `type` | `task` `bug` `epic` `dashboard` | clase de tarjeta (coincide con la carpeta) |
| `affects` | `[T-0NN, ...]` | (bugs/mejoras) tarjeta `done` cuyo código está implicado |
| `origin` | ruta | traza a la task de `tasks/` migrada (omitido en trabajo nuevo) |
| `created` | `YYYY-MM-DD` | fecha de creación |

Enlaces: siempre `[[T-0NN-slug|T-0NN]]` (Obsidian resuelve por nombre de archivo). En el
frontmatter, solo el id.

### Épicas (temáticas)
- [[E-base]] — esqueleto, `.env`, clientes AWS, salida, errores, protecciones y `config`.
- [[E-csv]] — generar y validar CSV de campaña.
- [[E-ingesta]] — `s3` y `lambda`: poner un CSV en el flujo.
- [[E-dynamo]] — tablas de campañas y de logs del ingester.
- [[E-logs]] — CloudWatch Logs.
- [[E-trace]] — prueba de punta a punta `trace run`.
- [[E-calidad]] — validación en dev, CI y documentación.

### Bugs y backlog vivo
- **`done` es inmutable** (registro de auditoría). Un bug o mejora sobre código ya hecho
  nunca reabre la tarjeta: se crea una nueva con `affects: [T-0NN]` y el enlace
  `[[T-0NN-slug|T-0NN]]` en el cuerpo (ejemplo: [[T-012-dynamo-purge|T-012]] amplía T-006).
- Los bugs van en `bugs/` con `_templates/bug.md`, normalmente sin `depends_on`, y su
  `## Verificación` exige una prueba de regresión que falle antes del fix y pase después.
- La épica de un bug es la **capacidad afectada** (`E-dynamo`, `E-logs`…); no existe `E-bugs`.
- Funcionalidades nuevas: `_templates/task.md`, siguiente `T-0NN` libre.
- **Triage** (escala de este proyecto):
  - `P0` la CLI no arranca, una protección falla (escribe en prod, borra datos que no son de
    `CLI_TEST_APP_ID`) o se filtran credenciales; o bloquea todo lo demás.
  - `P1` la prueba da un resultado incorrecto (falso OK/FALLA, IDs equivocados) o el trabajo
    está en el camino crítico hacia `trace run`.
  - `P2` molestia con workaround o mejora con valor claro (opciones nuevas, CI, documentación).
  - `P3` cosmético (formato de tablas, textos de ayuda).

### Ideas sin tarjeta (fase 2)
Del plan original; se convierten en tarjetas cuando haya alcance claro:
- Grupo `kafka`: publicar un evento en el topic del scheduler (MSK con IAM) para probar `platform_campaigns_ms` aislado.
- Grupo `mq`: inspeccionar las colas de RabbitMQ (Amazon MQ) vía API de administración.
- `trace run` hasta los adapters out, validando `CorrelationId = notification_id` en cada componente (complementa la HU 7938050).
- Escenarios guardados (`scenarios/*.yaml`) para correr baterías de pruebas con un comando.

## Plugins de Obsidian
- **Dataview** (imprescindible): todas las vistas; `ready-queue` usa `dataviewjs`
  (actívalo en los ajustes del plugin).
- **Templater** (recomendado): crear tarjetas desde `_templates/`.
- **Obsidian Git** (opcional): commits desde Obsidian.

Las consultas usan `FROM "backlog/tasks" OR "backlog/bugs"`, así que hay que abrir
**`campaigns-cli/`** como vault (es la raíz respecto de la cual está `backlog/`); así `docs/`
queda en el mismo vault y los enlaces entre ambos funcionan.

## Estado actual

✅ **done (5)**
- [[T-001-esqueleto-uv|T-001]] — proyecto uv, entry point `campaigns`, ruff/mypy/pytest.
- [[T-002-settings-env|T-002]] — `Settings`, `.env`/`--env-file`, `config show`.
- [[T-003-aws-output-guards|T-003]] — `AwsClients`, salida tabla/JSON, exit codes, guards, `config check`.
- [[T-006-dynamo-lectura|T-006]] — `dynamo get/find/list/logs` de solo lectura.
- [[T-008-logs-cloudwatch|T-008]] — `logs groups/tail/search` sobre las lambdas.

🟡 **todo (4)**
- [[T-004-csv-generate-validate|T-004]] — `csv generate` y `csv validate`.
- [[T-011-validar-lectura-dev|T-011]] — probar en dev `config check`, `dynamo` y `logs` con datos reales.
- [[T-012-dynamo-purge|T-012]] — `dynamo purge` de datos de `CLI_TEST_APP_ID`.
- [[T-014-ci-github-actions|T-014]] — pipeline de GitHub Actions con umbral de cobertura.

🔵 **backlog (5)**
- [[T-005-s3-commands|T-005]] — `s3 upload/ls/get/rm` (espera a T-004).
- [[T-007-lambda-invoke|T-007]] — `lambda invoke` ingester/scheduler/genérico (espera a T-005).
- [[T-009-trace-run|T-009]] — `trace run` hasta los logs del ingester (espera a T-004, T-005, T-012).
- [[T-010-documentacion|T-010]] — README completo y cierre de los criterios de aceptación (espera a T-007, T-009).
- [[T-013-trace-aguas-abajo|T-013]] — `trace run` con scheduler y microservicios (espera a T-007, T-009).

## Grafo de dependencias (resumido)
```
base:        T-001 ─► T-002 ─► T-003
dynamo:      T-003 ─► T-006 ─► T-012
logs:        T-003 ─► T-008
ingesta:     T-001 ─► T-004 ─► T-005 ─► T-007        (T-005 y T-007 también ─◄ T-003)
trace:       T-004, T-005, T-006, T-008, T-012 ─► T-009 ─► T-013 ◄─ T-007
docs:        T-007, T-009 ─► T-010
validación:  T-003, T-006, T-008 ─► T-011
ci:          T-001 ─► T-014
sin dependencias: T-001
```
