---
id: T-034
aliases: [T-034]
title: "Grupos E2E de rendimiento por el queuer en SC_whatsappJMeterTest.jmx"
status: backlog
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
- [ ] Variables nuevas con valores por defecto retrocompatibles: `V_queuerServer`, `V_pathQueuerCampaigns` (`/artemis/platform/queuer/v1/campaigns`), `V_pathQueuerNotifications`, `usersCampaignsQueuer` / `rampUpCampaignsQueuer` / `campaignsQueuerDuration` / `campaignsQueuerTps` y sus equivalentes de notificaciones (todos en `0`).
- [ ] `GH_campaignsQueuer` y `GH_notificationsQueuer` como `ConcurrencyThreadGroup` con `startnextloop`, igual que `GH_campaigns` / `GH_notifications`, con su Throughput Shaping Timer, `DT_Campaigns` y `User Parameters` por iteración.
- [ ] `metadata.Id` único por petición con prefijo de corrida (`qe2e-${V_runId}-${__UUID}`), que es la key del mensaje en Kafka y permite separarlo en [[T-036-validacion-kafka-e2e-rendimiento|T-036]].
- [ ] `Tx_campaignsQueuerTest` / `Tx_notificationsQueuerTest` → `HTTPSamplerProxy` `POST` al queuer con `Authorization: Bearer ${__P(access_token)}` y el mismo body que arman hoy `ReqPublishAndValidate*Kafka` (metadata en PascalCase, `applicationIdentifier` del dataset).
- [ ] Aserciones: código `202` y `$.status == accepted`.
- [ ] Reutilizar `ReqInteraction2Campaigns` / `ReqInteraction2Notifications` para verificar la entrega. Usar una clave de `SSLContext` propia del grupo y revisar si los 20 intentos alcanzan con la latencia añadida del queuer.
- [ ] Contador en `props` de `202` por flujo (`qe2e.campaigns.accepted`, `qe2e.notifications.accepted`) para [[T-036-validacion-kafka-e2e-rendimiento|T-036]].

## Criterios de aceptación
- [ ] Con los usuarios del queuer en `0`, una corrida de los grupos existentes genera las mismas transacciones que antes del cambio.
- [ ] Una corrida corta en QA (1 TPS, 60 s, demás grupos en `0`) tiene solo respuestas `202` y la entrega verificada en el fakechannel en todas las iteraciones.
- [ ] No hay dos peticiones de la corrida con el mismo `metadata.Id`.

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
