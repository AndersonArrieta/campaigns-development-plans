---
id: T-041
aliases: [T-041]
title: "Reutilizar el pool de usuarios de Teams en los grupos del queuer con shareMode.all"
status: done
priority: P2
epic: E-e2e-rendimiento
estimate: S
depends_on: [T-034]
type: task
created: 2026-11-09
---

# T-041 — Reutilizar el pool de usuarios de Teams en los grupos del queuer con `shareMode.all`

## Objetivo
Eliminar las copias invertidas `DT_CampaignUsersPool_Queuer.txt` / `DT_CampaignUsersPool_Reverse_Queuer.txt` de [[T-035-e2e-rendimiento-queuer-teams|T-035]] y hacer que `GH_campaignsQueuer` / `GH_notificationsQueuer` de `SC_teamsJMeterTest.jmx` lean los mismos archivos que los grupos directos (`DT_CampaignUsersPool.txt` / `DT_CampaignUsersPool_Reverse.txt`), con un puntero de lectura compartido (`shareMode.all`). Así cada usuario sale una sola vez entre el grupo directo y el del queuer en la misma corrida (`get-messages` de Teams consume el mensaje), sin duplicar datos que habrá que reemplazar cuando haya usuarios válidos.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)
- Separación actual de usuarios: notas del 2026-11-04 en [[T-035-e2e-rendimiento-queuer-teams|T-035]]

## Archivos a crear/modificar
- `Back/E2E/teams/SC_teamsJMeterTest.jmx` (4 `CSVDataSet` de usuarios)
- `Back/E2E/teams/campaigns/DT_CampaignUsersPool_Queuer.txt` (eliminar)
- `Back/E2E/teams/campaigns/DT_CampaignUsersPool_Reverse_Queuer.txt` (eliminar)
- `docs/pruebas.md` (sección de E2E de rendimiento, si menciona las copias)

## Tareas
- [ ] Confirmar con el equipo dueño de los scripts E2E que acepta cambiar `shareMode` de los `CSVDataSet` de usuarios de `GH_campaigns` / `GH_notifications` de Teams (`group` → `all`).
- [x] `DT_CampaignUsersPool` de `GH_campaigns` y `DT_CampaignUsersPoolQueuer` de `GH_campaignsQueuer`: los dos con `filename` = `campaigns/DT_CampaignUsersPool.txt` y `shareMode.all`. La ruta debe ser idéntica en ambos (JMeter identifica el puntero compartido por nombre de archivo + modo).
- [x] Igual para `GH_notifications` / `GH_notificationsQueuer` con `campaigns/DT_CampaignUsersPool_Reverse.txt`.
- [x] Mantener `recycle`, `ignoreFirstLine`, `stopThread`, delimitador y nombres de variables (`V_chatter`, `V_getMessagesId`) como están.
- [x] Eliminar las dos copias `_Queuer.txt` y revisar que ningún otro elemento las use.
- [x] Actualizar `docs/pruebas.md` y anotar en [[T-035-e2e-rendimiento-queuer-teams|T-035]] que la separación de usuarios ahora la hace el puntero compartido.

## Criterios de aceptación
- [x] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones y lee los usuarios en el mismo orden que antes del cambio.
- [x] Con un grupo directo y su grupo del queuer activos a la vez, ningún `V_chatter` se repite entre los dos mientras las iteraciones sumadas no superen las filas del archivo.
- [x] Las copias `_Queuer.txt` ya no existen ni se referencian en el `.jmx`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E/teams
grep -c '_Queuer.txt' SC_teamsJMeterTest.jmx    # esperado: 0
grep -A12 'testname="DT_CampaignUsersPool' SC_teamsJMeterTest.jmx | grep -E 'filename|shareMode'
# Copia temporal sin Tx_secretManager, sin publicación en Kafka ni POST al queuer (samplers reemplazados
# por un JSR223 que registra V_chatter), directos y queuer con varios usuarios: ningún V_chatter repetido
# entre GH_campaigns y GH_campaignsQueuer, ni entre GH_notifications y GH_notificationsQueuer.
# Usuarios del queuer en 0: mismas muestras que HEAD.
```

## Notas
- Opción A de la revisión del 2026-11-09 sobre los pools de Teams. Alternativas descartadas: mismo archivo con `shareMode.group` (los dos grupos empiezan en la línea 1 y se pisan) y leer el original desde otra línea con Groovy (más lógica en el `.jmx`).
- Cambia los `CSVDataSet` de los grupos directos. Cuando corren solos, `all` y `group` leen igual; el comportamiento solo cambia si otro grupo lee el mismo archivo en la misma corrida. Aun así, requiere el visto bueno del equipo dueño antes de llevarlo a la rama.
- Con `recycle=true`, cuando entre los dos grupos se consumen todas las filas el puntero vuelve al inicio y se repiten usuarios (mismo límite que con las copias). [[T-037-ejecucion-e2e-rendimiento-qa|T-037]] debe tenerlo en cuenta al definir el perfil de carga.
- No resuelve el bloqueo de [[T-035-e2e-rendimiento-queuer-teams|T-035]] (el pool no recibe entregas en QA). Conviene hacerla antes de reemplazar el pool con usuarios válidos, para actualizar solo los dos archivos originales; la corrida corta de T-035 se repite después.
- 2026-11-09 — Implementado en la rama `feature/8016357-queuer-e2e-performance-test` del repo PE, sin commit: en `SC_teamsJMeterTest.jmx` los 4 `CSVDataSet` de usuarios pasan a `shareMode.all` y los dos del queuer apuntan a `campaigns/DT_CampaignUsersPool.txt` / `campaigns/DT_CampaignUsersPool_Reverse.txt` (6 líneas, CRLF, XML válido). Las copias `_Queuer.txt` se eliminaron con `git rm` (borrado en el índice). Ningún otro elemento las usaba. `docs/pruebas.md` explica cómo se separan los usuarios en Teams.
- 2026-11-09 — Verificación local (JMeter 5.5 de WSL). Sin plugins (`casutg` / `tst`) en ninguna instalación, el `.jmx` completo no carga, así que se armó un plan mínimo con 4 `ThreadGroup` estándar, los `CSVDataSet` copiados tal cual del `.jmx` (HEAD y modificado) y un Debug Sampler que registra `V_chatter`:
  - Solo los directos (3 hilos × 20, queuer en `0`): HEAD y la versión modificada leen los mismos 60 usuarios por grupo, desde `usuario01` / `01usuario`.
  - Directos y queuer a la vez (5 hilos × 40 por grupo): 200 + 200 lecturas distintas por flujo y **0 usuarios cruzados** en campañas y en notificaciones.
  - Control: la configuración de HEAD (`shareMode.group`) con el queuer apuntando al archivo original cruza los 200 usuarios. Lo que evita el cruce es `shareMode.all`.
- Sin marcar, no bloquea el cierre: (1) el visto bueno del equipo dueño de los scripts E2E para cambiar `shareMode` en los grupos directos; pedirlo antes del commit/PR. (2) La corrida del `.jmx` completo con los usuarios del queuer en `0` (mismas muestras que HEAD) no se hizo por falta de plugins; el diff solo toca los 4 `CSVDataSet` y el plan mínimo muestra la misma lectura.
- 2026-11-10 — El equipo pidió volver a `shareMode.group` (grupo de hilos actual) en los 4 `CSVDataSet` de usuarios: [[T-043-pool-teams-sharemode-group|T-043]]. Al hacerlo, los grupos del queuer necesitan otra vez archivos con usuarios distintos a los de los directos.
