---
id: T-035
aliases: [T-035]
title: "Grupos E2E de rendimiento por el queuer en SC_teamsJMeterTest.jmx"
status: backlog
priority: P1
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-034]
type: task
created: 2026-11-04
---

# T-035 — Grupos E2E de rendimiento por el queuer en `SC_teamsJMeterTest.jmx`

## Objetivo
Replicar en `Back/E2E/teams/SC_teamsJMeterTest.jmx` los grupos `GH_campaignsQueuer` y `GH_notificationsQueuer` de [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]], con las particularidades de Teams.

## Documentación relacionada
- [Contrato de `POST /campaigns`](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Contrato de `POST /notifications`](../../docs/endpoints/POST-api-v1-notifications.md)

## Archivos a crear/modificar
- `Back/E2E/teams/SC_teamsJMeterTest.jmx`

## Tareas
- [ ] Mismas variables, grupos, aserciones y contadores que en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]].
- [ ] Usuarios desde el pool de Teams (`DT_CampaignUsersPool.txt` / `DT_CampaignUsersPool_Reverse.txt`: `V_chatter` = correo, `V_getMessagesId` para `get-messages`) y `sourceChannel` = `msteams`.
- [ ] Verificación de la entrega con `ReqInteraction2*` de Teams (`type = "message"`, consulta por `V_getMessagesId`).
- [ ] Evitar que los grupos del queuer y los directos usen los mismos usuarios del pool en la misma corrida, para que `get-messages` no devuelva el mensaje de otro grupo.

## Criterios de aceptación
- [ ] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones que antes del cambio.
- [ ] Una corrida corta en QA (1 TPS, 60 s, demás grupos en `0`) tiene solo respuestas `202` y la entrega verificada en el fakechannel en todas las iteraciones.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E/teams
jmeter -n -t SC_teamsJMeterTest.jmx -l /tmp/qe2e-teams.jtl -q <secretos>.properties \
  -JusersCampaignsQueuer=1 -JcampaignsQueuerTps=1 -JcampaignsQueuerDuration=60 \
  -JusersNotificationsQueuer=1 -JnotificationsQueuerTps=1 -JnotificationsQueuerDuration=60
awk -F, 'NR>1 && $3 ~ /Queuer/ {n++; if($8!="true") e++} END {print n" muestras, "e+0" fallidas"}' /tmp/qe2e-teams.jtl
```

## Notas
- Teams no se probó a mano por el queuer en [[T-015-prerrequisitos-e2e-qa|T-015]]; la primera corrida corta sirve como esa comprobación.
