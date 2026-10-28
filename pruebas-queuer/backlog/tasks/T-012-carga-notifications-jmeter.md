---
id: T-012
aliases: [T-012]
title: "Grupo de carga JMeter para POST /notifications"
status: done
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
- [x] Crear `GH_notifications` (`ConcurrencyThreadGroup`) con `V_usersNotifications`, `V_rampUpNotifications` y `V_durationNotifications`.
- [x] Agregar `jp@gc - Throughput Shaping Timer notifications` con `V_notificationsTps`.
- [x] Agregar `CSVDataSet` `DT_notifications` con `sourceChannel` y `message` (textos cortos de prueba, sin datos personales reales).
- [x] Agregar `User Parameters notifications` por iteración: `V_notMessageId = qmod-${V_runId}-${__UUID}`, `V_notificationId`, `V_chatter`, `V_dataTime` y `V_isoTime`.
- [x] Crear `Tx_modQueuerNotifications` → `Req_notifications` (`POST ${V_pathNotifications}`) con:
  - `metadata` en PascalCase, con `Source = performance:queuer-modular`;
  - `applicationIdentifier = ${V_kafkaAppId}`.
- [x] Agregar las mismas aserciones que [[T-011-carga-campaigns-jmeter|T-011]]: `202`, `$.status == accepted` y duración.
- [x] Agregar el contador `qmod.notifications.accepted` en `props` para [[T-013-validacion-kafka-modular|T-013]].

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
- 2026-10-28 — Implementado en la rama `feature/7993195-queuer-ms-kafka-modular` del repo PE: `GH_notifications` es una copia de `GH_campaigns` ([[T-011-carga-campaigns-jmeter|T-011]]) con sus propias variables (`V_notificationsTps`, `V_usersNotifications`, `V_rampUpNotifications`, `V_durationNotifications`), `Tx_modQueuerNotifications` / `Req_notifications` (`POST ${V_pathNotifications}`), `metadata.Type` = `notification.execute` (como el contrato), `messageContext` vacío y el contador `qmod.notifications.accepted` (+171 líneas, CRLF). `DT_notifications.txt`: 9 filas (`WhatsApp`, `msteams`, `SHP` × 3 textos de prueba sin datos personales). XML válido y body JSON válido.
- 2026-10-28 — Mock local con los dos grupos a la vez (3 TPS cada uno, 15 s): 35 `Req_campaigns` y 35 `Req_notifications`, cada uno con su transacción por separado, 0 fallos y todos los `metadata.Id` distintos. Entorno igual que T-011: JMeter 5.5, JRE 17 y plugins por `-Jsearch_paths`, con el Backend Listener desactivado en la copia local.
- 2026-10-28 — Corrida 1 en QA (`notificationsTps=1`, `usersNotifications=2`, `rampUpNotifications=5`, `durationNotifications=60`): 32 `Req_notifications`, todas `202`; las 2 primeras (una por hilo) tardaron **30,3 s y 29,0 s**, lo que bajó el TPS efectivo a 0,52. p50 150 ms. Es un arranque en frío del lado del servicio (ver [observación 5](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)): la corrida de T-011 había terminado unos 10 min antes, el TTL de la cache del secreto.
- 2026-10-28 — Corrida 2 en QA, justo después: 62 `Req_notifications`, todas `202`, 0,97 TPS, p50 120 ms, p95 199 ms. 2 fallos (3,2 %) por la aserción de 2000 ms: #1 (2266 ms) y #60 (2113 ms), el mismo patrón que en T-011.
- Cerrada como `done` con el mismo criterio que [[T-011-carga-campaigns-jmeter|T-011]]: el grupo cumple y los fallos son latencia del servicio; el umbral se fija en [[T-014-ejecucion-modular-qa|T-014]]. Quedan sin marcar el criterio de 0 % de errores y la separación de transacciones en Elasticsearch (solo comprobable desde el release; en el `.jtl` local sí salen separadas).
