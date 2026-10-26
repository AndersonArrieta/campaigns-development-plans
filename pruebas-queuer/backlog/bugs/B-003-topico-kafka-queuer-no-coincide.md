---
id: B-003
aliases: [B-003]
title: "La validación en Kafka lee un tópico donde el queuer no publica para others-test"
status: blocked
priority: P1
epic: E-aceptacion
estimate: S
depends_on: []
type: bug
affects: [T-025, T-026]
created: 2026-10-26
---

# B-003 — La validación en Kafka lee un tópico donde el queuer no publica para `others-test`

## Reproducción
- **Pasos:**
  1. En Windows, con VPN y credenciales AWS, ejecutar la suite de aceptación con `-DkafkaSecretName=nu0284001-artemis-dev-secret-operative-eda-composicion-nmt -DkafkaBatchTopic=customerforeignsubsidiarycampaignexecution.initiatecampaignv1 -DkafkaOnlineTopic=customerforeignsubsidiarycampaignmanagement.executenotificationv1` (2026-10-26 14:53).
- **Esperado:** AC-C01 recibe `202` y el helper encuentra en `kafkaBatchTopic` el mensaje con key = `metadata.Id`.
- **Observado:**
  - AC-C01 recibe `202`. El consumidor lee el secreto, arma el truststore PEM, hace login SASL, obtiene la metadata y se asigna las 3 particiones de `customerforeignsubsidiarycampaignexecution.initiatecampaignv1`.
  - `offsetsForTimes` no devuelve offsets, así que hace `seekToEnd`, y el último offset de **las 3 particiones es 0**: el tópico está vacío. A los 60 s: `No se encontro mensaje ... con key=qacc-b3b7df76-...`.
  - AC-C02, AC-N01 y AC-N02 fallan antes, con `Failed to construct kafka consumer`, porque la máquina local dejó de resolver `strimzi-com-nmt-dev.apps.ambientesbc.com` (y `broker-0-...` nunca resolvió). Es un problema de DNS/VPN local, no del código.
  - El resto de la suite pasa: 32/36.

## Causa (si se conoce)
- Si el queuer hubiera publicado el mensaje de AC-C01 en ese tópico unos 20 s antes, el último offset sería al menos 1. Con offset 0 en todas las particiones, el queuer **no publica en `kafkaBatchTopic`** para `others-test`. Puede publicar en otro tópico o en otro clúster: el queuer usa el `secret_campaigns` del segmento, que puede apuntar a un bootstrap distinto del de `kafkaSecretName`.
- [[T-025-datos-validacion-kafka-aceptacion|T-025]] asumió, sin verificarlo, que `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` del release de `platform_campaigns_ms` coinciden con `kafka.campaigns`, `kafka.notifications` y `secret_campaigns` del segmento de `others-test`. La aceptación de `platform_campaigns_ms` publica ella misma en su tópico, así que su uso no prueba esa equivalencia.
- Riesgo adicional: el consumidor usa `allow.auto.create.topics=true` (valor por defecto). Con un nombre de tópico equivocado podría crear un tópico en `dev` si el broker lo permite.

## Criterios de aceptación
- [x] Identificados, desde la configuración de segmentos de `dev`, el segmento de `others-test` y sus `kafka.campaigns`, `kafka.notifications` y `secret_campaigns` (solo nombres).
- [x] La suite lee del tópico y del clúster donde realmente publica el queuer: con los valores correctos en `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName`, o con propiedades nuevas si difieren de las de `platform_campaigns_ms`.
- [x] `KafkaManager` usa `allow.auto.create.topics=false`.
- [ ] Desde una red que resuelva los brokers (VPN estable o el agente del release), los 4 escenarios `202` encuentran su mensaje: 36/36.

## Verificación
```bash
# 1) Configuracion real del segmento (solo lectura, con credenciales AWS de dev)
aws dynamodb get-item --region us-east-1 \
  --table-name nu0284001-artemis-chatbots-platform-dev-config-data \
  --key '{"component":{"S":"platform-segments-destinies-config-map-v1"},"config_name":{"S":"config.json"}}' \
  --output json > /tmp/segmentos.json
# Buscar el segmento que contiene "others-test" y sus claves kafka.campaigns, kafka.notifications y secret_campaigns.

# 2) Comprobar en que topico quedo el mensaje del queuer: logs del pod en dev al hacer POST /campaigns
#    (el Handler/adaptador registra el topico de publicacion).

# 3) Suite con los valores correctos (36/36)
./gradlew clean test ... -DkafkaSecretName=<secret_campaigns> -DkafkaBatchTopic=<kafka.campaigns> -DkafkaOnlineTopic=<kafka.notifications>
```

## Notas
- **DNS local:** `nslookup broker-0-strimzi-com-nmt-dev.apps.ambientesbc.com` y `nslookup strimzi-com-nmt-dev.apps.ambientesbc.com` deben resolver antes de correr la suite en local. Si la VPN no publica esos nombres, la validación solo se podrá ejecutar desde el release.
- Si el tópico real del queuer difiere del de `platform_campaigns_ms`, las variables del release de aceptación del queuer **no** pueden enlazar las de `platform_campaigns_ms`: hay que crear variables propias, y corregir T-025 y `docs/pruebas.md`.
- La lectura de DynamoDB y de los logs es de solo lectura. No modificar la configuración de segmentos.
- 2026-10-26 — **Causa confirmada** con la configuración real de `dev` ([[T-030-script-leer-segmento-kafka|T-030]]):

  | Segmento | `applicationIdentifier` de prueba | `kafka.campaigns` | `kafka.notifications` | `secret_campaigns` |
  |---|---|---|---|---|
  | `others` | `others-test` (el que usa la suite) | `thirdpartycampaignexecution.initiatecampaignv1` | `thirdpartycampaignmanagement.executenotificationv1` | `nu0284001-artemis-dev-secret-operative-eda-experiencia-trv` |
  | `client-countries` | `client-countries-test` | `customerforeignsubsidiarycampaignexecution.initiatecampaignv1` | `customerforeignsubsidiarycampaignmanagement.executenotificationv1` | `nu0284001-artemis-dev-secret-operative-eda-composicion-nmt` |

  Las variables `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` del release de `platform_campaigns_ms` corresponden al segmento `client-countries`, no a `others`. El queuer publicó en los tópicos `thirdparty*` de otro clúster (otro secreto), por eso el tópico leído estaba vacío.
- **Opciones de corrección (decisión del usuario):**
  - **A. Cambiar `kafkaAppId` a `client-countries-test`.** Las variables actuales ya coinciden y el secreto `composicion-nmt` ya autenticó y leyó metadata en la corrida del usuario. No requiere cambios de código ni variables nuevas, solo cambiar el valor de `kafkaAppId` en el release (y en T-003 y `docs/pruebas.md`). Contra: cambia el app de prueba aprobado en T-003 (`others-test`); las campañas y notificaciones de prueba pasan a los tópicos de filiales del exterior, que también consume `platform_campaigns_ms`.
  - **B. Mantener `others-test` y apuntar a `others`.** Variables propias en el release del queuer: `kafkaBatchTopic` = `thirdpartycampaignexecution.initiatecampaignv1`, `kafkaOnlineTopic` = `thirdpartycampaignmanagement.executenotificationv1`, `kafkaSecretName` = `...-experiencia-trv`. Contra: no está probado que el usuario de `experiencia-trv` pueda leer esos tópicos ni crear un consumer group con prefijo `queuer-acceptance-` (posibles ACL de Strimzi); hay que confirmarlo con el equipo dueño.
- En ambos casos queda pendiente `allow.auto.create.topics=false` en `KafkaManager` y corregir T-025 y `docs/pruebas.md`, que afirman que las variables de `platform_campaigns_ms` aplican a `others-test`.
- 2026-10-26 15:23 — **Decisión del usuario: opción B (`others`).** Corrida local con `-DkafkaAppId=others-test -DkafkaBatchTopic=thirdpartycampaignexecution.initiatecampaignv1 -DkafkaOnlineTopic=thirdpartycampaignmanagement.executenotificationv1 -DkafkaSecretName=nu0284001-artemis-dev-secret-operative-eda-experiencia-trv`: **35/36**.
  - Secreto `experiencia-trv` leído; bootstrap `strimzi-exp-trv-dev.apps.ambientesbc.com:443`; truststore PEM; login SASL OK; asignación de particiones y lectura permitidas (sin errores de autorización de tópico ni de grupo).
  - AC-C02: mensaje encontrado en `thirdpartycampaignexecution.initiatecampaignv1` (partición 1, offset 6281). AC-N01 y AC-N02: encontrados en `thirdpartycampaignmanagement.executenotificationv1` (offsets 5080 y 5081). `data` e id de `metadata` validados.
  - AC-C01: `Failed to get offsets by times in 60013ms`. Fue el primer consumidor de la corrida: `UnknownHostException` para `broker-1-strimzi-exp-trv-dev...` y luego timeouts de conexión a ese broker (10.36.60.8 / 10.36.61.43). Es red local, no lógica: los consumidores siguientes conectaron con la misma configuración.
  - Evidencia de la [observación 1](../../docs/observaciones.md#1-el-mensaje-publicado-cambia-el-casing-de-metadata): las claves de `metadata` publicadas son `specVersion, dataSchema, id, source, time, type, dataContentType` (camelCase).
- **Pendiente para cerrar:**
  1. `KafkaManager`: `allow.auto.create.topics=false`; y reintentar `offsetsForTimes` ante `TimeoutException` (por ejemplo, hasta 2 intentos dentro de `kafkaMessageWaitSeconds`) para tolerar fallos transitorios de red sin perder el mensaje (no usar `seekToEnd` como respaldo, porque saltaría el mensaje ya publicado).
  2. Release de aceptación del queuer: variables **propias** `kafkaBatchTopic`, `kafkaOnlineTopic` y `kafkaSecretName` con los valores de `others` (no enlazar las de `platform_campaigns_ms`).
  3. Corregir T-025 (decisión), `docs/pruebas.md` y el README de `acceptanceTest` con los valores de `others`.
  4. 36/36 desde el release (o con red local estable).
- 2026-10-26 — Ejecutado en `feature/7978702_queuer_acceptance_tests`. Sin commit.
- Regresión (antes del fix, con `jshell` y un certificado autofirmado de prueba, sin red): `consumerProperties()` no define `allow.auto.create.topics` (queda el `true` por defecto). Después del fix: `allow.auto.create.topics=false`.
- Fix en `KafkaManager`: `allow.auto.create.topics=false`; `offsetsForTimesConReintentos`, que hace hasta 3 intentos de 30 s ante `TimeoutException`, sin respaldo con `seekToEnd`, y al agotarlos lanza `IllegalStateException: No se pudieron obtener los offsets de <topico> tras 3 intentos de 30 s`. Probado contra un broker inexistente (`localhost:1`): 2 avisos de reintento y la excepción a los 90 s. `compileTestJava` OK con `release 8`.
- Documentación: README de `acceptanceTest` (`kafkaSecretName`, `kafkaBatchTopic`, `kafkaOnlineTopic` = valores del segmento de `kafkaAppId`, con los de `others-test`, y el comportamiento de reintentos y `allow.auto.create.topics`), `docs/pruebas.md` (datos de prueba y propiedades) y nota de corrección en T-026. T-025 es `done` y no se edita: la corrección de su decisión queda en esta tarjeta.
- **blocked:** falta (1) que el usuario cree las variables propias del release de aceptación del queuer con los valores de `others`, y (2) 36/36 desde el release o con red local estable.
