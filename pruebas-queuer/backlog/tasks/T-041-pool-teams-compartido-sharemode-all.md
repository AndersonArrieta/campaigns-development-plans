---
id: T-041
aliases: [T-041]
title: "Reutilizar el pool de usuarios de Teams en los grupos del queuer con shareMode.all"
status: backlog
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
- [ ] `DT_CampaignUsersPool` de `GH_campaigns` y `DT_CampaignUsersPoolQueuer` de `GH_campaignsQueuer`: los dos con `filename` = `campaigns/DT_CampaignUsersPool.txt` y `shareMode.all`. La ruta debe ser idéntica en ambos (JMeter identifica el puntero compartido por nombre de archivo + modo).
- [ ] Igual para `GH_notifications` / `GH_notificationsQueuer` con `campaigns/DT_CampaignUsersPool_Reverse.txt`.
- [ ] Mantener `recycle`, `ignoreFirstLine`, `stopThread`, delimitador y nombres de variables (`V_chatter`, `V_getMessagesId`) como están.
- [ ] Eliminar las dos copias `_Queuer.txt` y revisar que ningún otro elemento las use.
- [ ] Actualizar `docs/pruebas.md` y anotar en [[T-035-e2e-rendimiento-queuer-teams|T-035]] que la separación de usuarios ahora la hace el puntero compartido.

## Criterios de aceptación
- [ ] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones y lee los usuarios en el mismo orden que antes del cambio.
- [ ] Con un grupo directo y su grupo del queuer activos a la vez, ningún `V_chatter` se repite entre los dos mientras las iteraciones sumadas no superen las filas del archivo.
- [ ] Las copias `_Queuer.txt` ya no existen ni se referencian en el `.jmx`.

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
