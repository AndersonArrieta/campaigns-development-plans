---
id: T-013
aliases: [T-013]
title: "Validar en Kafka al cierre de la prueba modular que cada 202 quedó publicado"
status: backlog
priority: P2
epic: E-modular
estimate: L
depends_on: [T-011, T-012]
type: task
created: 2026-10-22
---

# T-013 — Validar en Kafka al cierre de la prueba modular que cada `202` quedó publicado

## Objetivo
El `202` se devuelve después del ack de Kafka. Bajo carga hay que comprobar que esa promesa se cumple: el número de mensajes de la corrida en cada tópico debe coincidir con el número de `202`, sin pérdidas ni duplicados.

Se reutiliza el patrón de `SC_campaigns.jmx`:
- `Req_secretManager` en el setUp;
- consumidor en un `PostThreadGroup` de tearDown.

De paso se deja evidencia del casing de `metadata` en el mensaje publicado ([observación 1](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata)).

## Documentación relacionada
- [Credenciales](../../docs/publicacion-kafka.md#2-credenciales-kafkasecretprovider)
- [Resiliencia y reintentos](../../docs/publicacion-kafka.md#4-resiliencia)
- Referencia: `Back/Modular/campaigns_ms/SC_campaigns.jmx` (`Req_secretManager`, `GH_tearDownKafkaValidation`, `Tx_validateCampaignsNotificationsTopics`).

## Archivos a crear/modificar
- `Back/Modular/queuer_ms/SC_queuer.jmx`

## Tareas
- [ ] Agregar las variables `V_awsAccessKey`, `V_awsSecretKey`, `V_awsSessionToken` (por defecto `xxx`), `V_secretKafka`, `V_campaignsTopic`, `V_notificationsTopic`, `V_kafkaSaslMechanism` (`SCRAM-SHA-512`) y `V_validateKafka` (por defecto `false`), con los valores de [[T-009-datos-carga-kafka-qa|T-009]].
- [ ] En `GH_setUp`, agregar `Req_secretManager`, adaptado del de `campaigns_ms`. Solo debe ejecutarse si `V_validateKafka == true`, para que la corrida actual del release no pida credenciales AWS.
- [ ] Guardar en `props` el timestamp de inicio de la corrida.
- [ ] Agregar `GH_tearDownKafkaValidation` con `Tx_validateQueuerTopics`. Ese consumidor:
  - usa `assign()` sobre todas las particiones y `offsetsForTimes(inicio)`, **sin unirse al consumer group de `platform_campaigns_ms`**, para no mover sus offsets ni robarle mensajes;
  - si hace falta un `group.id`, usa uno efímero `qmod-validation-${V_runId}` con `enable.auto.commit=false`;
  - cuenta los mensajes cuya key empieza por `qmod-${V_runId}-` en cada tópico;
  - compara el conteo con `qmod.campaigns.accepted` y `qmod.notifications.accepted`, con un timeout configurable (90 s, como en `campaigns_ms`).
- [ ] Agregar la muestra informativa `Chk_metadataCasing`: toma el primer mensaje de la corrida y registra si `metadata` viene en PascalCase o camelCase. No falla la prueba, porque es un defecto conocido.
- [ ] Agregar la muestra `Tx_closeKafkaConsumer_Final`, que cierra el cliente y borra el truststore temporal.

## Criterios de aceptación
- [ ] Con `-JvalidateKafka=true`, una corrida corta en QA termina con `Tx_validateQueuerTopics` en éxito y el conteo coincide en ambos tópicos.
- [ ] Con `-JvalidateKafka=false` (valor por defecto) no hay llamadas a Secrets Manager ni a Kafka.
- [ ] Los offsets del consumer group de `platform_campaigns_ms` no cambian por la validación.
- [ ] Ninguna credencial queda en el `.jmx` ni en los logs (`log.info` sin usuario ni password).

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/Modular/queuer_ms
jmeter -n -t SC_queuer.jmx -l /tmp/qmod-kafka.jtl -JvalidateKafka=true \
  -JclientId="$CLIENT_ID" -JclientSecret="$CLIENT_SECRET" \
  -JawsAccessKey="$AWS_ACCESS_KEY_ID" -JawsSecretKey="$AWS_SECRET_ACCESS_KEY" -JawsSessionToken="$AWS_SESSION_TOKEN" \
  -JcampaignsTps=1 -JusersCampaigns=2 -JdurationCampaigns=60 \
  -JnotificationsTps=1 -JusersNotifications=2 -JdurationNotifications=60 -Jduration=60
grep -E 'Tx_validateQueuerTopics|Chk_metadataCasing' /tmp/qmod-kafka.jtl
grep -c -i -E 'password|secret' jmeter.log   # esperado: 0 líneas con valores sensibles
```

## Notas
- Una diferencia en el conteo debe registrarse como bug `B-0NN`: más mensajes que `202` indica duplicados por reintentos del productor; menos indica pérdida.
