---
id: T-035
aliases: [T-035]
title: "Grupos E2E de rendimiento por el queuer en SC_teamsJMeterTest.jmx"
status: blocked
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
- [x] Mismas variables, grupos, aserciones y contadores que en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]].
- [x] Usuarios desde el pool de Teams (`DT_CampaignUsersPool.txt` / `DT_CampaignUsersPool_Reverse.txt`: `V_chatter` = correo, `V_getMessagesId` para `get-messages`) y `sourceChannel` = `msteams`.
- [x] Verificación de la entrega con `ReqInteraction2*` de Teams (`type = "message"`, consulta por `V_getMessagesId`).
- [x] Evitar que los grupos del queuer y los directos usen los mismos usuarios del pool en la misma corrida, para que `get-messages` no devuelva el mensaje de otro grupo.

## Criterios de aceptación
- [x] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones que antes del cambio.
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
- 2026-11-04 — Implementado en la rama `feature/8016357-queuer-e2e-performance-test` del repo PE, sin commit. `SC_teamsJMeterTest.jmx` tiene +577 líneas, solo adiciones y en CRLF. Se agregan dos archivos de datos.
  - Mismas variables, grupos, aserciones, contadores y Throughput Shaping Timer (hijo del `POST`, con perfil `rampUp + duration + 300 s`) que en [[T-034-e2e-rendimiento-queuer-whatsapp|T-034]]. Transacciones `Tx_campaignsQueuerTeamsTest` / `Tx_notificationsQueuerTeamsTest`, por la convención `Tx_*TeamsTest` del script; [[T-037-ejecucion-e2e-rendimiento-qa|T-037]] debe incluirlas. El body es el de `ReqPublishAndValidate*Kafka` de Teams: `sourceChannel` = `msteams` desde `DT_Campaigns.txt`, `userIdentifier` = `V_chatter` (correo) y `Source` = `mapper:teams` en notificaciones. `ReqInteraction2*` de Teams se copia sin cambios (`recipient.id` = `V_getMessagesId`, `type = "message"`).
  - Usuarios: no se pueden crear usuarios nuevos, porque cada correo necesita un `conversationId` existente en el fakechannel (los `V_getMessagesId` son UUIDv5 de origen desconocido). Los grupos del queuer leen copias invertidas de los pools: `campaigns/DT_CampaignUsersPool_Queuer.txt` y `campaigns/DT_CampaignUsersPool_Reverse_Queuer.txt` (1000 usuarios cada uno, del 1000 al 01). Los directos leen desde la línea 1, así que no comparten usuarios mientras iteraciones directas + del queuer ≤ 1000 por pool en una corrida. Campañas usa el pool `usuarioNN` y notificaciones el `NNusuario`, igual que los directos.
- 2026-11-04 — Verificación local (mismo entorno que T-034: JMeter 5.5 + JRE 17 + plugins, Backend Listener desactivado solo en copias temporales):
  - Usuarios del queuer en `0`: `HEAD` y la versión modificada generan las mismas muestras.
  - Mock local: 120 peticiones, 120 `metadata.Id` distintos `qe2e-<runId>-*`, `sourceChannel` `msteams`, usuarios de campañas solo del pool `usuarioNN` y de notificaciones solo del `NNusuario`, sin cruce.
- 2026-11-04 — Corrida corta en QA, con aprobación del usuario (copia temporal sin `Tx_secretManager`, directos en `0`, 15 usuarios por grupo, 1 TPS, 60 s): 41 campañas y 40 notificaciones, **81/81 `202`** (`POST` p95 477 ms / 9,1 s), pero **0/81 entregas**. `ReqInteraction2*` recibe `404 No messages found for user <conversationId>` en los 20 intentos. Dos minutos después siguen sin mensajes.
- 2026-11-04 — Diagnóstico con aprobación del usuario, por el queuer y `ext-qa`:
  - Notificaciones Teams a `usuario01` (`f81e10cf-…`, el primero del pool, que usa el grupo directo), `usuario500` (`47b6d0de-…`) y `usuario1000` (`f0091175-…`): `202`, y ninguna entregada en 40 s.
  - Control a `sepiedra@ambientesbc.com` (`27060555-ecc0-4aad-85b6-9a663cd04331`, el usuario de [[T-017-e2e-notificaciones-queuer|T-017]]): `202`, entregada a los 10 s.
  - Conclusión: Teams entrega lo que entra por el queuer, pero ningún usuario del pool de Teams recibe mensajes en QA. No es un defecto de `queuer_ms` (el body es el mismo y el control llega), así que no se abre bug. No se pudo comprobar si el grupo directo `GH_campaigns` de Teams entrega hoy a esos usuarios: correrlo exige el secreto Kafka, que `FullStackQARole` no puede leer.
  - `get-messages` de Teams **consume** el mensaje: el control apareció en la primera lectura y en la siguiente dio `404`. Si dos grupos usan el mismo usuario a la vez, uno puede quedarse con el mensaje del otro y fallar (no da falso positivo).
- **Bloqueada:** el pool de usuarios de Teams (`DT_CampaignUsersPool*.txt`) no recibe entregas en QA. Siguiente paso: confirmar con el equipo dueño de los scripts E2E si esos usuarios siguen registrados en el fakechannel / adaptador de Teams de QA (¿la corrida del release de `GH_campaigns` Teams pasa hoy?), o conseguir un pool de usuarios Teams válidos (correo + `conversationId`) para los grupos del queuer. Con usuarios válidos, repetir la corrida corta.
- 2026-11-05 — Pasos para desbloquear:
  1. Revisar en Azure DevOps la última ejecución del release E2E de Teams: si `Tx_campaignsTeamsTest` / `Tx_notificationsTeamsTest` (grupos directos, mismos usuarios `usuario01`…) también fallan, el pool no sirve en QA para nadie y es tema del equipo dueño de los scripts E2E. Si pasan, comparar en el tópico un mensaje directo con uno del queuer.
  2. Preguntar al equipo dueño de los scripts E2E / adaptador de Teams si los usuarios `usuarioNN@` / `NNusuario@ambientesbc.com` siguen registrados en QA (el adaptador de salida necesita una conversación existente por usuario) y cómo se generaron los `V_getMessagesId`. Son UUIDv5 y el del control `sepiedra@` es UUIDv4, lo que sugiere (sin confirmar) otro mecanismo de alta. Si no siguen registrados, pedir que los registren de nuevo o un pool nuevo de correo + `conversationId` (unos 100 bastan para el queuer).
  3. Opcional, con acceso a logs de QA: buscar en el adaptador de salida de Teams los `metadata.Id` `qe2e-*` de la corrida del 2026-11-04; un error de conversación o usuario no encontrado confirma el diagnóstico.
  4. Alternativa limitada: 1 hilo por grupo con un usuario de control distinto por grupo (no uno compartido, porque `get-messages` consume el mensaje). Comprueba el flujo, pero no cumple el criterio (15 hilos, 1 TPS, 60 s); si se cierra así, el criterio queda sin marcar en Notas.
  5. Con usuarios válidos: reemplazar `DT_CampaignUsersPool_Queuer.txt` / `DT_CampaignUsersPool_Reverse_Queuer.txt`, repetir la corrida corta en QA, marcar el criterio, pasar a `done` y hacer commit en PE.
- 2026-11-05 — Diagnóstico repetido con aprobación del usuario (queuer por `ext-qa`, mismo body de `ReqNotificationsQueuer`, `appId` `performance_test`, run `diag20261105153107`):
  - Notificaciones a `usuario01` (`f81e10cf-…`), `usuario500` (`47b6d0de-0b8f-5749-a7ac-b153aea28990`) y `usuario1000` (`f0091175-…`): `202 accepted` (0,4–2,8 s), **ninguna entregada en 60 s**.
  - Control a `sepiedra@ambientesbc.com` (`27060555-…`): `202`, entregada a los 10 s.
  - `get-messages` de Teams consultado también por el correo, por `usuario01` y por el `conversationId`: `404` en todos. Los mensajes no quedan en el fakechannel con ninguna clave, así que el adaptador de salida de Teams no los entrega para esos usuarios (no es un problema de con qué id se consulta).
  - No se repitió la corrida corta completa (unos 80 mensajes reales en QA): con el pool sin cambios daría el mismo 0 % de entregas. Sigue bloqueada; el siguiente paso es el 1 o el 2 de la lista anterior.
- 2026-11-05 — Causa probable, por revisión de código (repo MR):
  - Para `msteams`, `platform_campaigns_ms` reemplaza el correo por el id de directorio activo antes de publicar al adaptador de salida (`UserResolverUseCase` → `UserDirectoryRestConsumer`, `GET <ms-authorization-endpoint>/users/basic-information?userId=<correo>&provider=azure`, de `platform_campaigns_Conf/platform-campaigns-dy.yaml`). Si `ms_authorization` no devuelve id, el mensaje falla con `No se pudo obtener el id del usuario: <correo>` y no llega al fakechannel. Eso coincide con el `404` por cualquier clave.
  - `ms_authorization` (`authorization_ms`, NestJS) no tiene lista propia: consulta Azure AD con `azure-adp-users-url` de la library del release (`authorization_Conf/authorization.yaml`). El fakechannel no simula ese directorio.
  - Fechas: la traducción correo → id se fusionó el 2026-08-24 (`db11dd481`, "Se realiza el mapeo del correo a id de ADP en campañas") y el pool de Teams se creó el 2026-09-03/04 en PE (`eabe81c` "Test e2e de campañas para teams funcionando", `be0f302` "se agregan mas correos con uuid correspondiente"). Así que el pool se armó para que el directorio que consulta `ms_authorization` en QA devuelva esos UUID. Hoy no los devuelve, o esa configuración cambió.
  - No confirmado en QA: `/artemis/platform/authorization{,/testing}/users/basic-information` por `ext-qa` responde `404` vacío también para `sepiedra@`, así que la ruta no está expuesta ahí. Listar DynamoDB de QA con la sesión de `queuer-qa.env` se denegó en la sesión.
  - Pregunta concreta para el equipo dueño (reemplaza al paso 2): ¿a qué apunta `azure-adp-users-url` en QA y dónde se dieron de alta los 2000 correos `usuarioNN@` / `NNusuario@ambientesbc.com` con sus UUID? Con el log de `platform_campaigns_ms` en QA, buscar `No se pudo obtener el id del usuario: usuario01@ambientesbc.com` (run `diag20261105153107`) lo confirma.
  - De E-modular no sale un pool válido: los datos `msteams` de `SC_queuer.jmx` usan `userIdentifier` aleatorio y nunca verificaron entrega. Lo reutilizable es el script modular `Back/Modular/authorization_ms/SC_authorization.jmx` (`users/complete-information`, `provider=azure`), que sirve para validar correos contra `ms_authorization` desde un agente con acceso a la ruta interna.
- 2026-11-09 — [[T-041-pool-teams-compartido-sharemode-all|T-041]]: los grupos del queuer ya no usan las copias invertidas `DT_CampaignUsersPool_Queuer.txt` / `DT_CampaignUsersPool_Reverse_Queuer.txt` (eliminadas). Leen los mismos pools que los directos con `shareMode.all` y la separación de usuarios la hace el puntero compartido. Al recibir usuarios válidos, basta con reemplazar `DT_CampaignUsersPool.txt` / `DT_CampaignUsersPool_Reverse.txt` (el paso 5 de arriba ya no aplica a las copias).
- 2026-11-10 — [[T-043-pool-teams-sharemode-group|T-043]]: los 4 `CSVDataSet` de usuarios vuelven a `shareMode.group` y los grupos del queuer leen otra vez copias invertidas (`DT_CampaignUsersPool_Queuer.txt` / `DT_CampaignUsersPool_Reverse_Queuer.txt`). Al recibir usuarios válidos, reemplazar los dos pools originales y regenerar las dos copias.
