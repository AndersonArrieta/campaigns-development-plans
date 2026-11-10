---
id: T-044
aliases: [T-044]
title: "Renombrar los samplers de los grupos E2E del queuer al estándar Req_XXX en WhatsApp y Teams"
status: backlog
priority: P2
epic: E-e2e-rendimiento
estimate: S
depends_on: [T-034]
type: task
created: 2026-11-10
---

# T-044 — Renombrar los samplers de los grupos E2E del queuer al estándar `Req_XXX` en WhatsApp y Teams

## Objetivo
Ajuste pedido por el equipo (2026-11-10): los samplers HTTP y Groovy (JSR223) de `GH_campaignsQueuer` y `GH_notificationsQueuer` deben seguir el estándar de nombres `Req_XXXXXX`, p. ej. `Req_NotificationsQueuer`, en `SC_whatsappJMeterTest.jmx` y en `SC_teamsJMeterTest.jmx`. Es el estándar que ya usan los demás grupos de los scripts (`Req_interaction1`, `Req_interaction0_transfersession`, …).

| Grupo | Tipo | Nombre actual | Nombre nuevo (propuesto) |
|---|---|---|---|
| `GH_campaignsQueuer` | HTTP (`POST` al queuer) | `ReqCampaignsQueuer` | `Req_CampaignsQueuer` |
| `GH_campaignsQueuer` | JSR223 (`get-messages`) | `ReqInteraction2Campaigns` | `Req_Interaction2CampaignsQueuer` |
| `GH_notificationsQueuer` | HTTP (`POST` al queuer) | `ReqNotificationsQueuer` | `Req_NotificationsQueuer` |
| `GH_notificationsQueuer` | JSR223 (`get-messages`) | `ReqInteraction2Notifications` | `Req_Interaction2NotificationsQueuer` |

Mismos 4 cambios en cada `.jmx` (8 en total). El sufijo `Queuer` en la verificación separa esas muestras de las de `ReqInteraction2*` de los grupos directos, que hoy tienen el mismo nombre y se mezclan en el `.jtl` y en Elasticsearch.

## Documentación relacionada
- [Guía de pruebas — E2E de rendimiento](../../docs/pruebas.md#pruebas-e2e-de-rendimiento-jmeter)
- [scripts/README.md](../../scripts/README.md)

## Archivos a crear/modificar
- `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx` (`testname` de 4 samplers)
- `Back/E2E/teams/SC_teamsJMeterTest.jmx` (`testname` de 4 samplers)
- `docs/pruebas.md` (sección de E2E de rendimiento: nombres de los samplers)
- `scripts/README.md` y el docstring de `scripts/e2e_rendimiento_queuer.py` (citan `ReqCampaignsQueuer` / `ReqNotificationsQueuer` / `ReqInteraction2*`)
- [[T-040-script-local-jmeter-e2e-rendimiento|T-040]] (el resumen separa las muestras por nombre de sampler)

## Tareas
- [ ] Confirmar los nombres de la verificación (`Req_Interaction2CampaignsQueuer` / `Req_Interaction2NotificationsQueuer`) con quien pidió el ajuste.
- [ ] Cambiar solo el `testname` de los 4 samplers en cada `.jmx`. Sin cambios en el body, las aserciones, el Throughput Shaping Timer, `Post_countAccepted*Queuer` ni los `Tx_*Queuer*Test`.
- [ ] Comprobar que ningún elemento referencia esos nombres como texto (hoy ninguno: no hay `getSampleLabel` ni filtros por nombre en los `.jmx`).
- [ ] Actualizar `docs/pruebas.md`, `scripts/README.md`, el docstring del script y el texto de [[T-040-script-local-jmeter-e2e-rendimiento|T-040]].

## Criterios de aceptación
- [ ] En los dos `.jmx`, los samplers de `GH_campaignsQueuer` / `GH_notificationsQueuer` siguen el formato `Req_XXX` y no queda ningún `ReqCampaignsQueuer` / `ReqNotificationsQueuer`.
- [ ] Los samplers de los grupos directos (`ReqPublishAndValidate*Kafka`, `ReqInteraction2*`) no cambian.
- [ ] El diff de cada `.jmx` solo toca atributos `testname` (CRLF, XML válido).
- [ ] Con los usuarios del queuer en `0`, `jmeter -n` genera las mismas muestras que antes del cambio.
- [ ] Contra un mock local o en una corrida corta aprobada por el usuario, el `.jtl` muestra las etiquetas nuevas dentro de las transacciones `Tx_*Queuer*Test`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E
grep -c -E 'testname="Req(Campaigns|Notifications)Queuer"' whatsapp/SC_whatsappJMeterTest.jmx teams/SC_teamsJMeterTest.jmx   # esperado: 0 y 0
grep -o -E 'testname="Req_[A-Za-z0-9]*Queuer"' whatsapp/SC_whatsappJMeterTest.jmx teams/SC_teamsJMeterTest.jmx              # esperado: 4 por archivo
git diff --ignore-cr-at-eol --stat -- whatsapp/SC_whatsappJMeterTest.jmx teams/SC_teamsJMeterTest.jmx
```

## Notas
- Pedido el 2026-11-10: "en los groovy o red toca hacer un ajuste; el estándar debe ser `Req_XXXXXX`, ejemplo `Req_NotificationsQueuer`; tanto para Teams como para WhatsApp".
- Fuera de alcance si no se pide: renombrar los samplers de los grupos directos (`ReqPublishAndValidate*Kafka`, `ReqInteraction2*`), que no son de esta épica, y el sampler del teardown `Tx_validateQueuerTopics` de [[T-036-validacion-kafka-e2e-rendimiento|T-036]], que sigue la convención `Tx_` del teardown existente (`Tx_validateCampaignsNotificationsTopics`). Preguntarlo al confirmar los nombres.
- Cambia las etiquetas en el `.jtl` y en Elasticsearch. Todavía no hay línea base ([[T-037-ejecucion-e2e-rendimiento-qa|T-037]]), así que no rompe comparaciones históricas.
- En Teams el código de [[T-035-e2e-rendimiento-queuer-teams|T-035]] ya está en la rama (`c72cd39`): el renombre no depende de su bloqueo. Si se hace junto con [[T-043-pool-teams-sharemode-group|T-043]], van en el mismo archivo de Teams; conviene un commit por tarjeta.
