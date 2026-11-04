---
id: T-034
aliases: [T-034]
title: "Grupos E2E de rendimiento por el queuer en SC_whatsappJMeterTest.jmx"
status: done
priority: P1
epic: E-e2e-rendimiento
estimate: M
depends_on: [T-033]
type: task
created: 2026-11-04
---

# T-034 — Grupos E2E de rendimiento por el queuer en `SC_whatsappJMeterTest.jmx`

## Objetivo
Agregar a `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx` dos grupos, `GH_campaignsQueuer` y `GH_notificationsQueuer`, que envíen campañas y notificaciones por `POST /campaigns` y `POST /notifications` del queuer, validen el `202` y verifiquen la entrega en el fakechannel. Desactivados por defecto (usuarios en `0`), para que las ejecuciones actuales no cambien.

## Documentación relacionada
- [Contrato de `POST /campaigns`](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Contrato de `POST /notifications`](../../docs/endpoints/POST-api-v1-notifications.md)
- Referencia del grupo modular: [[T-011-carga-campaigns-jmeter|T-011]] y [[T-012-carga-notifications-jmeter|T-012]]

## Archivos a crear/modificar
- `Back/E2E/whatsapp/SC_whatsappJMeterTest.jmx`

## Tareas
- [x] Variables nuevas con valores por defecto retrocompatibles: `V_queuerServer`, `V_pathQueuerCampaigns` (`/artemis/platform/queuer/v1/campaigns`), `V_pathQueuerNotifications`, `usersCampaignsQueuer` / `rampUpCampaignsQueuer` / `campaignsQueuerDuration` / `campaignsQueuerTps` y sus equivalentes de notificaciones (todos en `0`).
- [x] `GH_campaignsQueuer` y `GH_notificationsQueuer` como `ConcurrencyThreadGroup` con `startnextloop`, igual que `GH_campaigns` / `GH_notifications`, con su Throughput Shaping Timer, `DT_Campaigns` y `User Parameters` por iteración.
- [x] `metadata.Id` único por petición con prefijo de corrida (`qe2e-${V_runId}-${__UUID}`), que es la key del mensaje en Kafka y permite separarlo en [[T-036-validacion-kafka-e2e-rendimiento|T-036]].
- [x] `Tx_campaignsQueuerTest` / `Tx_notificationsQueuerTest` → `HTTPSamplerProxy` `POST` al queuer con `Authorization: Bearer ${__P(access_token)}` y el mismo body que arman hoy `ReqPublishAndValidate*Kafka` (metadata en PascalCase, `applicationIdentifier` del dataset).
- [x] Aserciones: código `202` y `$.status == accepted`.
- [x] Reutilizar `ReqInteraction2Campaigns` / `ReqInteraction2Notifications` para verificar la entrega. Usar una clave de `SSLContext` propia del grupo y revisar si los 20 intentos alcanzan con la latencia añadida del queuer.
- [x] Contador en `props` de `202` por flujo (`qe2e.campaigns.accepted`, `qe2e.notifications.accepted`) para [[T-036-validacion-kafka-e2e-rendimiento|T-036]].

## Criterios de aceptación
- [x] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones que antes del cambio.
- [x] Una corrida corta en QA (1 TPS, 60 s, demás grupos en `0`) tiene solo respuestas `202` y la entrega verificada en el fakechannel en todas las iteraciones.
- [x] No hay dos peticiones de la corrida con el mismo `metadata.Id`.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E/whatsapp
jmeter -n -t SC_whatsappJMeterTest.jmx -l /tmp/qe2e-whatsapp.jtl -q <secretos>.properties \
  -JusersCampaignsQueuer=1 -JcampaignsQueuerTps=1 -JcampaignsQueuerDuration=60 \
  -JusersNotificationsQueuer=1 -JnotificationsQueuerTps=1 -JnotificationsQueuerDuration=60
awk -F, 'NR>1 && $3 ~ /Queuer/ {n++; if($8!="true") e++} END {print n" muestras, "e+0" fallidas"}' /tmp/qe2e-whatsapp.jtl
```

## Notas
- Pasar los secretos (`cognitoSecret`, `awsSecretKey`, …) con `-q <archivo>.properties`: con `-J` quedan en `jmeter.log` (ver [[T-013-validacion-kafka-modular|T-013]]).
- Cada `202` produce un mensaje real en QA. Respetar los límites de carga acordados en [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]].
- 2026-11-04 — Implementado en la rama `feature/8016357-queuer-e2e-performance-test` del repo PE: +593 líneas en `SC_whatsappJMeterTest.jmx`, solo adiciones y en CRLF. Los grupos existentes no cambian.
  - Variables nuevas: `V_queuerServer` (`informacion-ext-qa.apps.ambientesbc.com`, de [[T-033-prerrequisitos-e2e-rendimiento-qa|T-033]]), `V_pathQueuerCampaigns` / `V_pathQueuerNotifications`, `V_campaignsQueuerDuration` / `V_campaignsQueuerTps` y las de notificaciones (en `0`), y `V_runId` (`${__time(yyyyMMddHHmmss)}`, igual que `SC_queuer.jmx`). Usuarios y rampa: `usersCampaignsQueuer` / `rampUpCampaignsQueuer` / `usersNotificationsQueuer` / `rampUpNotificationsQueuer` (en `0`).
  - `GH_campaignsQueuer` / `GH_notificationsQueuer`: `ConcurrencyThreadGroup` con `startnextloop`, `DT_Campaigns` (copia del grupo directo), `HTTP Header Manager` con `Bearer ${__P(access_token)}` y `User Parameters` por iteración (`V_queuerMessageId` = `qe2e-${V_runId}-${__UUID}`, `V_chatter` = `57` + 10 dígitos con `__RandomString`, UUIDs, `dataTime` y `Time` ISO-8601 UTC). `Tx_campaignsQueuerTest` / `Tx_notificationsQueuerTest` (`parent=true`, como los directos) contienen `ReqCampaignsQueuer` / `ReqNotificationsQueuer` (`POST` con el body de `ReqPublishAndValidate*Kafka`, metadata en PascalCase) y `ReqInteraction2Campaigns` / `ReqInteraction2Notifications` copiados sin cambios.
  - Aserciones: código `202` y `$.status == accepted`. `Post_countAccepted*Queuer` suma en `props` (`qe2e.campaigns.accepted`, `qe2e.notifications.accepted`, `AtomicLong`) cada `202`.
  - `SSLContext`: no hizo falta una clave propia. `ReqInteraction2*` guarda el contexto en `vars`, que es de cada hilo, así que no se comparte entre grupos.
  - Throughput Shaping Timer: en los grupos existentes está desactivado (`enabled="false"`). En los nuevos va **activado** y es hijo del `POST`, así que solo limita las peticiones al queuer y no `ReqInteraction2*`. Su perfil dura `rampUp + duration + 300 s`, para que el grupo termine por su `Hold`. En la primera corrida, el timer a nivel de grupo limitaba también la verificación (~0,2 TPS). Además, al acabar el perfil apagaba el motor completo (`Tries more than 5, shutting down engine!`), lo que en una corrida mixta cortaría los grupos directos.
- 2026-11-04 — Verificación local (JMeter 5.5 + JRE 17 + plugins `casutg` 2.10 y `tst` 2.6, librerías de `@Grab` desde la caché de Ivy con `-Dgroovy.grape.enable=false`, Backend Listener de Elasticsearch desactivado solo en las copias temporales, credenciales con `-q` sin rastro en `jmeter.log`):
  - Usuarios del queuer en `0`: la versión de `HEAD` y la modificada generan las mismas muestras (`Tx_oauthToken` OK, `Tx_secretManager` falla). Con la identidad `FullStackQARole` de `queuer-qa.env`, `GetSecretValue` sobre el secreto Kafka da `AccessDenied` ([[T-013-validacion-kafka-modular|T-013]]).
  - Corrida corta en QA, con aprobación del usuario: copia temporal con `Tx_secretManager` desactivado (con `stoptest` en `GH_setup` no corre ningún grupo sin el secreto), grupos directos en `0`, 15 usuarios por grupo, 1 TPS, 60 s. Resultado: 43 campañas y 41 notificaciones, **84/84 `202`** y entrega verificada en el primer intento en todas. `POST` p95 521 ms (campañas) y 468 ms (notificaciones); transacción completa p95 1,26 s y 1,10 s. Sin errores. El timer da ~0,7 TPS efectivos. Una corrida previa con el timer a nivel de grupo publicó 27 mensajes más (26 `202` entregados y 1 petición cortada por el apagado del motor).
  - Contra un mock local (sin QA): 100 peticiones, 100 `metadata.Id` distintos con el prefijo `qe2e-<runId>-`, `userIdentifier` siempre de 12 dígitos y bodies JSON válidos.
- Pendientes, sin bloquear el cierre: la corrida desde el release necesita una identidad que lea el secreto Kafka, porque `GH_setup` lo exige aunque solo corran los grupos del queuer. Hacer opcional `Tx_secretManager` cambiaría el setup existente; queda para [[T-036-validacion-kafka-e2e-rendimiento|T-036]] o una tarjeta nueva. Con `Tx_preTestCampaignKafka` desactivado, el teardown actual nunca recibe `setup.status`; lo revisa T-036.
