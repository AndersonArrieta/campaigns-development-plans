# Backlog — `pruebas-queuer` (modo agente)

Vault de Obsidian versionado con git (repo `campaigns-development-plans`) con el trabajo de pruebas de los endpoints Kafka REST proxy de `queuer_ms` (`POST /api/v1/campaigns` y `POST /api/v1/notifications`, rama `feature/7931497-queuer-ms-kafka-rest-proxy`). Lo ejecuta un agente IA tarjeta a tarjeta; el orden de trabajo lo dicta el **grafo de dependencias + prioridad**, no un calendario. No sustituye ningún plan previo.

El código que se modifica vive en el repo `NU0284001_Artemis_Chatbots_Platform_MR` (`queuer_ms/deployment/acceptanceTest` y `queuer_ms/deployment/smokeTest`, proyectos Karate) y, para las pruebas modulares de rendimiento, en el repo `NU0284001_Artemis_Chatbots_Platform_PE` (`Back/Modular/queuer_ms`, JMeter, ambiente QA), y para las E2E funcionales en el repo `NU0284001_Artemis_Chatbots_Platform_MR_Test` (`Platform_test` + `queuer_ms_test`, Serenity, ambiente QA). Este backlog y la documentación viven aquí, en `pruebas-queuer/`.

## Modelo

- **El frontmatter es la única fuente de verdad.** Todas las vistas (tablero, ready queue, épicas, roadmap) se generan con Dataview; no hay listas mantenidas a mano.
- **La [[ready-queue]] es el driver**: dice qué tarjeta está desbloqueada y cuál va primero.
- **Añadir trabajo = crear un `.md`** en `tasks/` o `bugs/` a partir de `_templates/`, con el siguiente id libre.
- **Backlog vs. documentación**: el backlog dice *qué hay que cambiar*; [`../docs/`](../docs/README.md) dice *cómo funcionan hoy* los endpoints y qué se prueba. Cada tarjeta enlaza la doc que necesita, y cuando una tarjeta cambia qué se prueba o cómo se ejecuta, actualiza [`../docs/pruebas.md`](../docs/pruebas.md).
- No se usan ADRs: este backlog no toma decisiones de arquitectura del microservicio.

### Bucle de ejecución del agente
```
mientras existan tareas no-done:
    ready = tareas con status ∈ {backlog, todo} y todas sus depends_on = done
    siguiente = ready ordenada por priority (P0 → P3)
    → poner status: doing
    → implementar (+ ./gradlew clean test en acceptanceTest/smokeTest contra dev, o jmeter -n contra QA, si aplica)
    → correr el bloque "## Verificación" de la tarjeta
    → si pasa: status: done ; si no: status: blocked + nota
```

El agente puede computar la cola leyendo el frontmatter de `tasks/` y `bugs/`; **no necesita Obsidian** (Obsidian es solo la capa visual para humanos). Para ejecutar una tarjeta: pasa [`_prompts/execute-task.md`](_prompts/execute-task.md) como mensaje de sistema y el id (`T-001`) como mensaje de usuario.

### Estructura
```
pruebas-queuer/
├── docs/                   # documentación de los endpoints (cómo funciona hoy)
└── backlog/
    ├── _templates/
    │   ├── task.md             # plantilla de tarea/funcionalidad (T-0NN)
    │   └── bug.md              # plantilla de bug (B-0NN)
    ├── _prompts/
    │   └── execute-task.md     # system prompt: ejecuta UNA tarjeta (le pasas el id)
    ├── tasks/                  # T-0NN-<slug>.md
    ├── bugs/                   # B-0NN-<slug>.md
    ├── epics/                  # E-<tema>.md con su Dataview
    ├── dashboards/
    │   ├── ready-queue.md      # ⭐ cola del agente
    │   ├── board.md            # Kanban por status
    │   ├── bugs.md             # bugs abiertos/cerrados
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
| `origin` | ruta | traza a un plan previo (no se usa: todo el trabajo es nuevo) |
| `created` | `YYYY-MM-DD` | fecha de creación |

### Épicas (temáticas)
- [[E-entorno]] — parametrización Karate, exposición de rutas por Istio/Cognito y datos de prueba en `dev`.
- [[E-aceptacion]] — escenarios de aceptación de `/api/v1/campaigns` y `/api/v1/notifications`.
- [[E-humo]] — escenarios de humo sin efectos en Kafka.
- [[E-trazabilidad]] — ejecución en `dev`, evidencias y trazabilidad con `docs/`.
- [[E-modular]] — pruebas modulares de rendimiento (JMeter, QA) en el repo PE, con validación en Kafka.
- [[E-e2e]] — E2E funcionales (Serenity, QA): del queuer a la entrega en el fakechannel.
- [[E-seguridad]] — hallazgos del análisis de contenedor (DevSecOps) que bloquean el release de `queuer_ms`.

### Bugs y backlog vivo
- **`done` es inmutable.** Un bug o mejora sobre trabajo ya cerrado crea una tarjeta nueva que enlaza la anterior con `affects:` y `[[T-0NN-slug|T-0NN]]`.
- Los bugs van en `bugs/` con la plantilla `_templates/bug.md`; su épica es la **capacidad afectada** (nunca un cajón `E-bugs`), y su `## Verificación` exige una prueba de regresión que falle antes del fix y pase después.
- Candidatos a bug ya identificados en la revisión: [observaciones](../docs/observaciones.md) 1–4 (se proponen al cerrar [[T-007-evidencias-y-trazabilidad|T-007]]).
- Funcionalidades nuevas: plantilla `_templates/task.md`.
- **Triage:**
  - `P0` la suite de humo o aceptación no puede ejecutarse en el pipeline / los endpoints no responden en `dev`.
  - `P1` escenarios que faltan para cubrir el contrato, resultados incorrectos del endpoint, riesgo de publicar a usuarios reales o de filtrar secretos.
  - `P2` evidencias, trazabilidad, mejoras con workaround.
  - `P3` cosmético.

## Plugins de Obsidian
- **Dataview** (imprescindible; `ready-queue` usa `dataviewjs` — actívalo en los ajustes del plugin).
- **Templater** (recomendado, para instanciar `_templates/`).
- **Obsidian Git** (opcional).

Las consultas usan `FROM "backlog/tasks" OR "backlog/bugs"`, así que hay que abrir **`pruebas-queuer/`** como vault (no la raíz de `campaigns-development-plans`).

## Estado actual
- ✅ **done (0)** — ninguna.
- 🟡 **todo (5)**
  - [[T-001-parametrizar-karate-config|T-001]] — `baseUrl`, `kafkaReadTimeout` y `kafkaAppId` en los `karate-config.js`, retrocompatible.
  - [[T-002-verificar-exposicion-rutas|T-002]] — confirmar que el VirtualService y Cognito dejan pasar `/api/v1/*` en `dev`.
  - [[T-003-datos-prueba-kafka-dev|T-003]] — `appId` de prueba con segmento Kafka completo y `appId` sin segmento.
  - [[T-008-exposicion-rutas-qa|T-008]] — rama desplegada y `/api/v1/*` enrutado en QA; paths para JMeter.
  - [[T-009-datos-carga-kafka-qa|T-009]] — `appId`, tópicos, secreto y efecto en el consumidor para la carga en QA.
- 🔵 **backlog (15)**
  - [[T-004-aceptacion-campaigns|T-004]] — 10 escenarios de aceptación de campañas.
  - [[T-005-aceptacion-notifications|T-005]] — 9 escenarios de aceptación de notificaciones.
  - [[T-006-humo-endpoints-kafka|T-006]] — 2 escenarios de humo sin publicar en Kafka.
  - [[T-007-evidencias-y-trazabilidad|T-007]] — ejecución en `dev`, evidencias y trazabilidad en `docs/pruebas.md`.
  - [[T-010-parametrizar-sc-queuer|T-010]] — variables nuevas en `SC_queuer.jmx` sin romper `GH_queuer`.
  - [[T-011-carga-campaigns-jmeter|T-011]] — grupo de carga de `POST /api/v1/campaigns`.
  - [[T-012-carga-notifications-jmeter|T-012]] — grupo de carga de `POST /api/v1/notifications`.
  - [[T-013-validacion-kafka-modular|T-013]] — validación en Kafka al cierre (conteo de `202` contra mensajes).
  - [[T-014-ejecucion-modular-qa|T-014]] — ejecución en QA, línea base y evidencias.
  - [[T-015-prerrequisitos-e2e-qa|T-015]] — prueba manual del queuer al fakechannel en QA, con los datos y propiedades E2E.
  - [[T-016-interaccion-envio-queuer|T-016]] — interacción Screenplay `SendEventThroughQueuer` y validación del `202`.
  - [[T-017-e2e-notificaciones-queuer|T-017]] — E2E de notificaciones por el queuer (WhatsApp y Teams).
  - [[T-018-e2e-campanas-queuer|T-018]] — E2E de campañas por el queuer (WhatsApp y Teams).
  - [[T-019-pipeline-queuer-ms-test|T-019]] — suite `Queuer` en el pipeline de `queuer_ms_test`.
  - [[T-020-ejecucion-e2e-qa|T-020]] — ejecución E2E en QA y evidencias.

## Grafo de dependencias (resumido)
```
karate-config:   T-001 ─► T-004, T-005, T-006
exposición:      T-002 ─► T-004, T-005, T-006
datos Kafka:     T-003 ─► T-004, T-005
trazabilidad:    T-004, T-005, T-006 ─► T-007
modular (QA):    T-008 ─► T-010 ─► T-011, T-012
                 T-009 ─► T-011, T-012
                 T-011, T-012 ─► T-013 ─► T-014   (T-014 también depende de T-011, T-012)
e2e (QA):        T-008 ─► T-015 ─► T-016 ─► T-017, T-018 ─► T-019 ─► T-020
sin dependencias: T-001, T-002, T-003, T-008, T-009
```
