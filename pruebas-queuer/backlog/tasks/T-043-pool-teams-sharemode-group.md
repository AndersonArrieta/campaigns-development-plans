---
id: T-043
aliases: [T-043]
title: "Leer el pool de usuarios de Teams por grupo de hilos (shareMode.group) en los grupos de campañas y notificaciones"
status: done
priority: P1
epic: E-e2e-rendimiento
estimate: S
depends_on: [T-041]
type: task
created: 2026-11-10
---

# T-043 — Leer el pool de usuarios de Teams por grupo de hilos (`shareMode.group`) en los grupos de campañas y notificaciones

## Objetivo
Ajuste pedido por el equipo (2026-11-10): los `CSVDataSet` de usuarios de `SC_teamsJMeterTest.jmx` deben compartir el puntero solo dentro del **grupo de hilos actual** (`shareMode.group`), no entre todos los hilos de la prueba (`shareMode.all`), para evitar que un grupo le pise los usuarios a otro.

Aplica a los 4 `CSVDataSet` de usuarios:

| Grupo | `CSVDataSet` | Archivo actual | `shareMode` actual |
|---|---|---|---|
| `GH_campaigns` | `DT_CampaignUsersPool` | `campaigns/DT_CampaignUsersPool.txt` | `shareMode.all` |
| `GH_notifications` | `DT_CampaignUsersPool` | `campaigns/DT_CampaignUsersPool_Reverse.txt` | `shareMode.all` |
| `GH_campaignsQueuer` | `DT_CampaignUsersPoolQueuer` | `campaigns/DT_CampaignUsersPool.txt` | `shareMode.all` |
| `GH_notificationsQueuer` | `DT_CampaignUsersPoolQueuer` | `campaigns/DT_CampaignUsersPool_Reverse.txt` | `shareMode.all` |

`SC_whatsappJMeterTest.jmx` no tiene pool de usuarios (el `userIdentifier` se genera por iteración), así que no cambia.

**Revierte la decisión de [[T-041-pool-teams-compartido-sharemode-all|T-041]].** Con `shareMode.group`, cada grupo tiene su propio puntero desde la línea 1. Si el grupo directo y el del queuer leen el **mismo archivo**, usan los mismos usuarios a la vez. En Teams, `get-messages` consume el mensaje, así que un grupo se puede quedar con el mensaje del otro y fallar la verificación ([[T-035-e2e-rendimiento-queuer-teams|T-035]]). Por eso, al pasar a `group`, los grupos del queuer deben leer archivos con usuarios distintos a los de los directos.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)
- Separación de usuarios: notas de [[T-035-e2e-rendimiento-queuer-teams|T-035]] (copias invertidas, 2026-11-04) y de [[T-041-pool-teams-compartido-sharemode-all|T-041]] (opciones descartadas)

## Archivos a crear/modificar
- `Back/E2E/teams/SC_teamsJMeterTest.jmx` (4 `CSVDataSet` de usuarios)
- `Back/E2E/teams/campaigns/DT_CampaignUsersPool_Queuer.txt` (nuevo, según la decisión de abajo)
- `Back/E2E/teams/campaigns/DT_CampaignUsersPool_Reverse_Queuer.txt` (nuevo, según la decisión de abajo)
- `docs/pruebas.md` (cómo se separan los usuarios en Teams)

## Tareas
- [x] Confirmar con quien pidió el ajuste cómo separar los usuarios entre el grupo directo y el del queuer:
  - **Recomendada:** archivos propios del queuer con el pool en orden invertido (`DT_CampaignUsersPool_Queuer.txt` y `DT_CampaignUsersPool_Reverse_Queuer.txt`, del usuario 1000 al 01), como en [[T-035-e2e-rendimiento-queuer-teams|T-035]]. Los directos no cambian de archivo. No se cruzan mientras iteraciones directas + del queuer ≤ 1000 por pool.
  - Alternativa: partir el pool en dos mitades disjuntas (p. ej. 01–500 para directos y 501–1000 para el queuer). No se cruzan nunca, pero cambia el archivo de los directos y deja 500 usuarios por grupo.
  - Si directos y queuer nunca van a correr en la misma corrida, se puede dejar el mismo archivo. [[T-037-ejecucion-e2e-rendimiento-qa|T-037]] hoy prevé correrlos juntos, así que habría que cambiarla.
- [x] Cambiar `shareMode` de los 4 `CSVDataSet` de `shareMode.all` a `shareMode.group`.
- [x] Apuntar `DT_CampaignUsersPoolQueuer` de los dos grupos del queuer a los archivos que se decidan.
- [x] Mantener `recycle`, `ignoreFirstLine`, `stopThread`, delimitador y nombres de variables (`V_chatter`, `V_getMessagesId`) como están.
- [x] Actualizar `docs/pruebas.md` y anotar el cambio en [[T-041-pool-teams-compartido-sharemode-all|T-041]] y [[T-035-e2e-rendimiento-queuer-teams|T-035]]. Al recibir usuarios válidos de Teams (bloqueo de T-035), hay que reemplazar también los archivos del queuer.

## Criterios de aceptación
- [x] Los 4 `CSVDataSet` de usuarios de `SC_teamsJMeterTest.jmx` tienen `shareMode.group`.
- [x] Con los usuarios del queuer en `0`, los grupos directos leen los mismos usuarios en el mismo orden que antes del cambio.
- [x] Con un grupo directo y su grupo del queuer activos a la vez, ningún `V_chatter` se repite entre los dos dentro del límite de filas acordado.
- [x] Dentro de un mismo grupo, con varios hilos, ningún `V_chatter` se repite mientras las iteraciones no superen las filas del archivo.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E/teams
grep -A12 'testname="DT_CampaignUsersPool' SC_teamsJMeterTest.jmx | grep -E 'testname|filename|shareMode'
# Esperado: 4 × shareMode.group; los dos DT_CampaignUsersPoolQueuer con los archivos decididos
# Plan mínimo como en T-041 (ThreadGroup estándar + CSVDataSet copiados tal cual + Debug Sampler con V_chatter):
#  - solo directos: mismos usuarios y orden que HEAD
#  - directos y queuer a la vez (varios hilos × iteraciones): 0 usuarios cruzados por flujo y 0 repetidos dentro de cada grupo
```

## Notas
- Pedido el 2026-11-10 para los grupos `GH_campaigns*` / `GH_notifications*` del queuer: "modificar al grupo de hilos actual; en este momento está compartiendo a todos los hilos y puede generar un problema de repisado".
- Cambia los `CSVDataSet` de los grupos directos (vuelven a `shareMode.group`, que era su valor antes de [[T-041-pool-teams-compartido-sharemode-all|T-041]]). El commit de T-041 (`2adcb2a`) ya está publicado en la rama del repo PE: el cambio va en un commit nuevo.
- No resuelve el bloqueo de [[T-035-e2e-rendimiento-queuer-teams|T-035]] (el pool no recibe entregas en QA).
- Con `recycle=true`, al agotar el archivo el grupo vuelve a la línea 1 y repite usuarios. [[T-037-ejecucion-e2e-rendimiento-qa|T-037]] debe acotar las iteraciones por grupo según el reparto decidido.
- 2026-11-10 — Decisión del usuario: copias invertidas (opción recomendada).
- 2026-11-10 — Implementado en la rama `feature/8016357-queuer-e2e-performance-test` del repo PE, sin commit:
  - `SC_teamsJMeterTest.jmx`: los 4 `CSVDataSet` de usuarios pasan a `shareMode.group` y los dos `DT_CampaignUsersPoolQueuer` apuntan a `campaigns/DT_CampaignUsersPool_Queuer.txt` / `campaigns/DT_CampaignUsersPool_Reverse_Queuer.txt`. Son 6 líneas (`git diff --ignore-cr-at-eol`) y el XML es válido. `recycle`, `ignoreFirstLine`, `stopThread`, delimitador y variables no cambian.
  - Las dos copias se restauraron desde `2adcb2a^` (las que eliminó [[T-041-pool-teams-compartido-sharemode-all|T-041]]). Se comprobó que son el pool actual de `HEAD` en orden invertido: 1000 filas + cabecera, del usuario 1000 al 01.
  - `docs/pruebas.md` (E2E de rendimiento) explica la separación nueva. Nota en [[T-035-e2e-rendimiento-queuer-teams|T-035]].
  - En WSL el `.jmx` y los pools aparecen modificados enteros por fin de línea (índice LF, árbol CRLF del checkout con `git.exe`). El cambio real son solo las 6 líneas; hacer el commit con `git.exe` o revisar con `--ignore-cr-at-eol`.
- 2026-11-10 — Verificación local (JMeter 5.5 + JRE 17). Plan mínimo con 4 `ThreadGroup` estándar, los `CSVDataSet` copiados tal cual del `.jmx` (`HEAD` y modificado) y un JSR223 que registra `grupo|V_chatter`:
  - Solo directos (3 hilos × 20): `HEAD` y la versión nueva leen los mismos 60 usuarios por grupo, desde `usuario01` / `01usuario`, contiguos y sin repetidos.
  - Directos y queuer a la vez (5 hilos × 40 por grupo): 200 + 200 lecturas por flujo, **0 usuarios cruzados** y 0 repetidos dentro de cada grupo. El queuer empieza en `usuario1000` / `1000usuario`.
  - Control: con `shareMode.group` y el queuer leyendo el archivo original, se cruzan los 200 usuarios. Las copias son necesarias.
  - El `.jmx` completo carga con `SaveService` (plugins `casutg` / `tst` / `cmn-jmeter`) y lista los 4 `CSVDataSet` con `shareMode.group` y los archivos esperados.
- Sin marcar, no bloquea el cierre: el commit en el repo PE (requiere confirmación del usuario) y la corrida del `.jmx` completo con `jmeter -n`, que no se hizo porque el diff solo toca los `CSVDataSet` y la carga y lectura se comprobaron con el plan mínimo.
