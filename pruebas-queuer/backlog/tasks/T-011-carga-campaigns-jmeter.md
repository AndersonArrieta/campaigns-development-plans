---
id: T-011
aliases: [T-011]
title: "Grupo de carga JMeter para POST /campaigns"
status: done
priority: P1
epic: E-modular
estimate: M
depends_on: [T-009, T-010]
type: task
created: 2026-10-22
---

# T-011 — Grupo de carga JMeter para `POST /campaigns`

## Objetivo
Agregar a `SC_queuer.jmx` un grupo que genere carga controlada por TPS sobre `POST /campaigns`. Cada petición debe llevar un `metadata.Id` único, que es la key del mensaje en Kafka y permite verificarlo en [[T-013-validacion-kafka-modular|T-013]]. El grupo valida tres cosas: `202`, el body de aceptación y el tiempo de respuesta.

## Documentación relacionada
- [Contrato de `POST /campaigns`](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Latencia atada a los reintentos de Kafka](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)

## Archivos a crear/modificar
- `Back/Modular/queuer_ms/SC_queuer.jmx`
- `Back/Modular/queuer_ms/DT_campaigns.txt` (nuevo)

## Tareas
- [x] Crear el grupo `GH_campaigns` como `ConcurrencyThreadGroup`, igual que `SC_campaigns.jmx` y `SC_translateUtilitiesMS.jmx`. Usar `V_usersCampaigns`, `V_rampUpCampaigns` y `V_durationCampaigns`, y `on_sample_error = startnextloop`.
- [x] Agregar `jp@gc - Throughput Shaping Timer campaigns` con rampa 1 → `V_campaignsTps` → sostenido → 1, igual que el grupo existente.
- [x] Agregar `CSVDataSet` `DT_campaigns` con `sourceChannel` y `messageContext` (nombre y apellido), reciclando los valores de `DT_Vars.txt`.
- [x] Agregar `User Parameters campaigns` **por iteración** (`per_iteration = true`):
  - `V_cmpMessageId = qmod-${V_runId}-${__UUID}`
  - `V_campaignId`, `V_notificationId` = `${__UUID}`
  - `V_chatter` según el criterio de [[T-009-datos-carga-kafka-qa|T-009]]
  - `V_dataTime = ${__time(yyyy-MM-dd HH:mm:ss)}`
  - `V_isoTime = ${__time(yyyy-MM-dd'T'HH:mm:ss'Z')}`
- [x] Crear `Tx_modQueuerCampaigns` → `Req_campaigns` (`POST ${V_pathCampaigns}`) con el payload del contrato:
  - `metadata` en PascalCase, con `Source = performance:queuer-modular`;
  - `applicationIdentifier = ${V_kafkaAppId}`.
- [x] Agregar las aserciones:
  - código `202`;
  - `JSONPathAssertion` `$.status == accepted`;
  - `DurationAssertion` `${V_assertionTimeout}`.
- [x] Agregar un `JSR223PostProcessor` que incremente un contador en `props` (`qmod.campaigns.accepted`) cuando la respuesta es `202`. Lo usa [[T-013-validacion-kafka-modular|T-013]].

## Criterios de aceptación
- [ ] Una corrida corta en QA (`campaignsTps=1`, `durationCampaigns=60`, demás grupos en `0`) tiene 0 % de errores y solo respuestas `202`.
- [x] No hay dos peticiones de la corrida con el mismo `metadata.Id`.
- [ ] Las métricas llegan a Elasticsearch con la etiqueta `Tx_modQueuerCampaigns`.

## Verificación
```bash
# JMeter 5.5 con plugins jpgc (Custom Thread Groups, Throughput Shaping Timer) y el Backend Listener de Elasticsearch
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms
jmeter -n -t SC_queuer.jmx -l /tmp/qmod-campaigns.jtl \
  -JclientId="$CLIENT_ID" -JclientSecret="$CLIENT_SECRET" \
  -JcampaignsTps=1 -JusersCampaigns=2 -JrampUpCampaigns=5 -JdurationCampaigns=60 -Jduration=60
awk -F, 'NR>1 && $3=="Req_campaigns" {n++; if($4!="202") e++} END {print n" peticiones, "e+0" no-202"}' /tmp/qmod-campaigns.jtl
```

## Notas
- El grupo existente `GH_queuer` usa `per_iteration = false` en sus `User Parameters`, así que repite `message_id` dentro de un mismo hilo. No se toca aquí. Si afecta a los resultados de VariableSetter, abrir una tarjeta aparte.
- Cada `202` produce un mensaje real que procesa `platform_campaigns_ms`. Antes de subir los TPS hay que coordinar con el equipo consumidor (ver [[T-009-datos-carga-kafka-qa|T-009]]).
- 2026-10-28 — Implementado en la rama `feature/7993195-queuer-ms-kafka-modular` del repo PE: grupo `GH_campaigns` (`ConcurrencyThreadGroup`, `startnextloop`, `TargetLevel`/`RampUp`/`Hold` = `V_usersCampaigns`/`V_rampUpCampaigns`/`V_durationCampaigns`) después de `GH_queuer` (+178 líneas, CRLF), y `DT_campaigns.txt` (69 filas de `DT_Vars.txt` sin `V_strServiceSuccess`; canales `WhatsApp`, `msteams` y `SHP`). `messageContext` = `{nombre, apellido}`. `V_chatter` = `57${__RandomString(10,0123456789)}`, para tener siempre 10 dígitos (`__Random(0000000000,…)` no rellena con ceros). El contador `qmod.campaigns.accepted` es un `AtomicLong` en `props` creado con `computeIfAbsent`, así no depende de que `GH_setUp` lo inicialice. XML válido y el body es JSON válido.
- El Throughput Shaping Timer copia el perfil de `GH_queuer`: tres tramos (1 → TPS, sostenido, TPS → 1) de `V_durationCampaigns` cada uno, mientras el grupo solo dura `V_durationCampaigns` (`Hold`). En la práctica solo se ejecuta el primer tramo, igual que en `GH_queuer`. Con `campaignsTps=1` no cambia nada; se revisa al definir el perfil en [[T-014-ejecucion-modular-qa|T-014]].
- 2026-10-28 — Entorno local: JMeter 5.5 en `/opt/apache-jmeter-5.5` (WSL) sin plugins en `lib/ext` (sin permisos de escritura). Los plugins `jmeter-plugins-casutg` 3.1.1, `jmeter-plugins-tst` 2.6 y `jmeter-plugins-cmn-jmeter` 0.9 se cargaron desde una carpeta aparte con `-Jsearch_paths`/`-Juser.classpath`. Con Java 21 el Groovy 3.0.11 de JMeter 5.5 falla (`Unsupported class file major version 65`) y no se ejecuta ningún `Req_campaigns`; se usó un JRE 17 (Temurin) portable. El Backend Listener se desactivó en una copia local del plan (no tiene URL de Elasticsearch fuera del release).
- 2026-10-28 — Corrida en QA (`campaignsTps=1`, `usersCampaigns=2`, `rampUpCampaigns=5`, `durationCampaigns=60`): 57 `Req_campaigns`, **todas `202`** con `$.status == accepted`, 0,93 TPS efectivos, p50 132 ms, p95 544 ms. **2 fallos (3,5 %) por la aserción de duración** (`assertionTimeout=2000`): la petición #1 (2518 ms, arranque en frío) y la #56 (2177 ms, a los 60 s). El criterio de 0 % de errores no se cumple con el umbral de 2000 ms; ver [observación 5](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka). El umbral se define en [[T-014-ejecucion-modular-qa|T-014]].
- 2026-10-28 — Unicidad de `metadata.Id` comprobada contra un mock local (OAuth + endpoint, 5 TPS, 3 hilos, 15 s): 52 peticiones, 52 `metadata.Id` distintos con forma `qmod-<runId>-<uuid>`, `userIdentifier` siempre de 12 dígitos, 0 fallos y sin errores en el log (incluido el `JSR223PostProcessor`).
- Detalle menor: `V_isoTime` (`${__time(yyyy-MM-dd'T'HH:mm:ss'Z')}`, tal como lo pide la tarjeta) usa la hora local con sufijo `Z`, así que `metadata.Time` queda 5 h corrido respecto a UTC. No afecta el `202`.
- Pendiente: métricas en Elasticsearch con la etiqueta `Tx_modQueuerCampaigns`, solo comprobable desde el release.
- 2026-10-28 — Cerrada como `done` por decisión del usuario: el grupo cumple (57/57 `202 accepted`, `metadata.Id` únicos). Los 2 fallos por duración son latencia del servicio, no del script; quedan para el umbral de [[T-014-ejecucion-modular-qa|T-014]]. Quedan sin marcar el criterio de 0 % de errores y el de Elasticsearch.
