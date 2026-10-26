---
id: T-012
aliases: [T-012]
title: "Grupo de carga JMeter para POST /notifications"
status: backlog
priority: P1
epic: E-modular
estimate: M
depends_on: [T-009, T-010]
type: task
created: 2026-10-22
---

# T-012 — Grupo de carga JMeter para `POST /notifications`

## Objetivo
Es el equivalente de [[T-011-carga-campaigns-jmeter|T-011]] para notificaciones en línea: un grupo con TPS independiente sobre `POST /notifications`, con `metadata.Id` único y marcado con el `runId`. Así se puede medir cada endpoint por separado o los dos a la vez.

## Documentación relacionada
- [Contrato de `POST /notifications`](../../docs/endpoints/POST-api-v1-notifications.md)

## Archivos a crear/modificar
- `Back/Modular/queuer_ms/SC_queuer.jmx`
- `Back/Modular/queuer_ms/DT_notifications.txt` (nuevo)

## Tareas
- [ ] Crear `GH_notifications` (`ConcurrencyThreadGroup`) con `V_usersNotifications`, `V_rampUpNotifications` y `V_durationNotifications`.
- [ ] Agregar `jp@gc - Throughput Shaping Timer notifications` con `V_notificationsTps`.
- [ ] Agregar `CSVDataSet` `DT_notifications` con `sourceChannel` y `message` (textos cortos de prueba, sin datos personales reales).
- [ ] Agregar `User Parameters notifications` por iteración: `V_notMessageId = qmod-${V_runId}-${__UUID}`, `V_notificationId`, `V_chatter`, `V_dataTime` y `V_isoTime`.
- [ ] Crear `Tx_modQueuerNotifications` → `Req_notifications` (`POST ${V_pathNotifications}`) con:
  - `metadata` en PascalCase, con `Source = performance:queuer-modular`;
  - `applicationIdentifier = ${V_kafkaAppId}`.
- [ ] Agregar las mismas aserciones que [[T-011-carga-campaigns-jmeter|T-011]]: `202`, `$.status == accepted` y duración.
- [ ] Agregar el contador `qmod.notifications.accepted` en `props` para [[T-013-validacion-kafka-modular|T-013]].

## Criterios de aceptación
- [ ] Una corrida corta en QA (`notificationsTps=1`, `durationNotifications=60`) tiene 0 % de errores y solo `202`.
- [ ] Corriendo `GH_campaigns` y `GH_notifications` a la vez, cada transacción aparece por separado en Elasticsearch.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms
jmeter -n -t SC_queuer.jmx -l /tmp/qmod-notifications.jtl \
  -JclientId="$CLIENT_ID" -JclientSecret="$CLIENT_SECRET" \
  -JnotificationsTps=1 -JusersNotifications=2 -JrampUpNotifications=5 -JdurationNotifications=60 -Jduration=60
awk -F, 'NR>1 && $3=="Req_notifications" {n++; if($4!="202") e++} END {print n" peticiones, "e+0" no-202"}' /tmp/qmod-notifications.jtl
```

## Notas
- Los dos endpoints comparten el secreto `secret_campaigns` y, por tanto, el productor Kafka del pod ([publicación en Kafka §3](../../docs/publicacion-kafka.md#3-productor-kafkaproducerconfig)). La carga combinada es la que mejor representa la contención real.
