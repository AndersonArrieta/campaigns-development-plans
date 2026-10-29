---
id: T-013
aliases: [T-013]
title: "Validar en Kafka al cierre de la prueba modular que cada 202 quedó publicado"
status: blocked
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
- [x] Agregar las variables `V_awsAccessKey`, `V_awsSecretKey`, `V_awsSessionToken` (por defecto `xxx`), `V_secretKafka`, `V_campaignsTopic`, `V_notificationsTopic`, `V_kafkaSaslMechanism` (`SCRAM-SHA-512`) y `V_validateKafka` (por defecto `false`), con los valores de [[T-009-datos-carga-kafka-qa|T-009]].
- [x] En `GH_setUp`, agregar `Req_secretManager`, adaptado del de `campaigns_ms`. Solo debe ejecutarse si `V_validateKafka == true`, para que la corrida actual del release no pida credenciales AWS.
- [x] Guardar en `props` el timestamp de inicio de la corrida.
- [x] Agregar `GH_tearDownKafkaValidation` con `Tx_validateQueuerTopics`. Ese consumidor:
  - usa `assign()` sobre todas las particiones y `offsetsForTimes(inicio)`, **sin unirse al consumer group de `platform_campaigns_ms`**, para no mover sus offsets ni robarle mensajes;
  - si hace falta un `group.id`, usa uno efímero `qmod-validation-${V_runId}` con `enable.auto.commit=false`;
  - cuenta los mensajes cuya key empieza por `qmod-${V_runId}-` en cada tópico;
  - compara el conteo con `qmod.campaigns.accepted` y `qmod.notifications.accepted`, con un timeout configurable (90 s, como en `campaigns_ms`).
- [x] Agregar la muestra informativa `Chk_metadataCasing`: toma el primer mensaje de la corrida y registra si `metadata` viene en PascalCase o camelCase. No falla la prueba, porque es un defecto conocido.
- [x] Agregar la muestra `Tx_closeKafkaConsumer_Final`, que cierra el cliente y borra el truststore temporal.

## Criterios de aceptación
- [ ] Con `-JvalidateKafka=true`, una corrida corta en QA termina con `Tx_validateQueuerTopics` en éxito y el conteo coincide en ambos tópicos.
- [x] Con `-JvalidateKafka=false` (valor por defecto) no hay llamadas a Secrets Manager ni a Kafka.
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
- 2026-10-28 — Implementado en la rama `feature/7993195-queuer-ms-kafka-modular` del repo PE (+342 líneas en `SC_queuer.jmx`, CRLF):
  - Variables nuevas: `V_validateKafka` (`false`), `V_awsAccessKey` / `V_awsSecretKey` / `V_awsSessionToken` / `V_secretKafka` (`xxx`), `V_campaignsTopic` / `V_notificationsTopic` (tópicos `thirdparty*` de [[T-009-datos-carga-kafka-qa|T-009]]), `V_kafkaSaslMechanism` (`SCRAM-SHA-512`) y `V_kafkaValidationTimeout` (`90`). El nombre del secreto no se versiona: se pasa con `secretKafka`.
  - `GH_setUp`: `If_validateKafka` → `Req_secretManager`. Guarda en `props` el inicio de la corrida (`qmod.test.start.ts`), el `runId` y la configuración Kafka (`qmod.kafka.*`, truststore PKCS12 temporal solo con el CA del secreto). Acepta credenciales sin `sessionToken`.
  - `GH_tearDownKafkaValidation` (`PostThreadGroup`) → `If_validateKafka` → `Tx_validateQueuerTopics`, `Chk_metadataCasing` y `Tx_closeKafkaConsumer_Final`. El consumidor no tiene `group.id`: usa `assign()` + `offsetsForTimes(inicio − 5 s)` + `seek()`, así que no se une a ningún consumer group ni confirma offsets. Lee hasta los `endOffsets` (o hasta el timeout), cuenta las keys `qmod-<runId>-*` por tópico y exige `conteo == qmod.*.accepted` y keys sin duplicados. `Chk_metadataCasing` siempre pasa y registra PascalCase/camelCase del primer mensaje. `Tx_closeKafkaConsumer_Final` cierra el consumidor, borra el truststore y limpia las `props` con credenciales.
- 2026-10-28 — Verificación con mock local (JMeter 5.5 + JRE 17):
  - `validateKafka=false`: solo muestras de `Tx_oauthToken`, `Req_campaigns` y `Req_notifications`; el tearDown arranca pero el `If` no ejecuta nada. Sin llamadas a Secrets Manager ni a Kafka.
  - `validateKafka=true`: `Req_secretManager` compila y llama a Secrets Manager. Con el rol SSO `FullStackQARole` → `AccessDeniedException` sobre `secret_campaigns` (igual que en [[T-009-datos-carga-kafka-qa|T-009]]); el setUp detiene la prueba (`stoptest`) y no corre la carga.
  - En local `@Grab` no resuelve dependencias (JMeter 5.5 no trae Ivy y Grape no se activa aunque se agregue). Se usó una copia de JMeter con `kafka-clients` 3.5.1 y `secretsmanager` 2.15.0 resueltos con Ivy en `lib/`. Hay que confirmar que el agente del release tiene Grape/Ivy o esas librerías, como para `SC_campaigns.jmx`.
- 2026-10-28 — **Credenciales en el log de JMeter:** JMeter registra cada `-J<propiedad>=<valor>` en `jmeter.log` (`Setting JMeter property: awsSecretKey=...`); afecta también a `clientSecret`, que el release ya pasa así. Pasar las propiedades sensibles en un archivo con `-q <archivo>.properties` no las registra (comprobado: solo aparece `Loading additional properties from: ...`). Los logs locales de estas pruebas se borraron.
- **Bloqueada:** el `Tx_validateQueuerTopics` real no se pudo ejecutar porque ninguna identidad disponible puede leer `secret_campaigns` en QA. Siguiente paso: dar a una identidad de las pruebas modulares `secretsmanager:GetSecretValue` sobre ese secreto (o usar la del release) y repetir la verificación con `-JvalidateKafka=true`. Pendientes: el conteo en ambos tópicos, que los offsets del consumer group de `platform_campaigns_ms` no cambien y cerrar el criterio de credenciales usando `-q`.
