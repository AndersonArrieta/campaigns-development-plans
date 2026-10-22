---
id: T-011
aliases: [T-011]
title: "Grupo de carga JMeter para POST /api/v1/campaigns"
status: backlog
priority: P1
epic: E-modular
estimate: M
depends_on: [T-009, T-010]
type: task
created: 2026-10-22
---

# T-011 — Grupo de carga JMeter para `POST /api/v1/campaigns`

## Objetivo
Agregar a `SC_queuer.jmx` un grupo que genere carga controlada por TPS sobre `POST /api/v1/campaigns`. Cada petición debe llevar un `metadata.Id` único, que es la key del mensaje en Kafka y permite verificarlo en [[T-013-validacion-kafka-modular|T-013]]. El grupo valida tres cosas: `202`, el body de aceptación y el tiempo de respuesta.

## Documentación relacionada
- [Contrato de `POST /api/v1/campaigns`](../../docs/endpoints/POST-api-v1-campaigns.md)
- [Latencia atada a los reintentos de Kafka](../../docs/observaciones.md#5-latencia-del-endpoint-atada-a-los-reintentos-de-kafka)

## Archivos a crear/modificar
- `Back/Modular/queuer_ms/SC_queuer.jmx`
- `Back/Modular/queuer_ms/DT_campaigns.txt` (nuevo)

## Tareas
- [ ] Crear el grupo `GH_campaigns` como `ConcurrencyThreadGroup`, igual que `SC_campaigns.jmx` y `SC_translateUtilitiesMS.jmx`. Usar `V_usersCampaigns`, `V_rampUpCampaigns` y `V_durationCampaigns`, y `on_sample_error = startnextloop`.
- [ ] Agregar `jp@gc - Throughput Shaping Timer campaigns` con rampa 1 → `V_campaignsTps` → sostenido → 1, igual que el grupo existente.
- [ ] Agregar `CSVDataSet` `DT_campaigns` con `sourceChannel` y `messageContext` (nombre y apellido), reciclando los valores de `DT_Vars.txt`.
- [ ] Agregar `User Parameters campaigns` **por iteración** (`per_iteration = true`):
  - `V_cmpMessageId = qmod-${V_runId}-${__UUID}`
  - `V_campaignId`, `V_notificationId` = `${__UUID}`
  - `V_chatter` según el criterio de [[T-009-datos-carga-kafka-qa|T-009]]
  - `V_dataTime = ${__time(yyyy-MM-dd HH:mm:ss)}`
  - `V_isoTime = ${__time(yyyy-MM-dd'T'HH:mm:ss'Z')}`
- [ ] Crear `Tx_modQueuerCampaigns` → `Req_campaigns` (`POST ${V_pathCampaigns}`) con el payload del contrato:
  - `metadata` en PascalCase, con `Source = performance:queuer-modular`;
  - `applicationIdentifier = ${V_kafkaAppId}`.
- [ ] Agregar las aserciones:
  - código `202`;
  - `JSONPathAssertion` `$.status == accepted`;
  - `DurationAssertion` `${V_assertionTimeout}`.
- [ ] Agregar un `JSR223PostProcessor` que incremente un contador en `props` (`qmod.campaigns.accepted`) cuando la respuesta es `202`. Lo usa [[T-013-validacion-kafka-modular|T-013]].

## Criterios de aceptación
- [ ] Una corrida corta en QA (`campaignsTps=1`, `durationCampaigns=60`, demás grupos en `0`) tiene 0 % de errores y solo respuestas `202`.
- [ ] No hay dos peticiones de la corrida con el mismo `metadata.Id`.
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
