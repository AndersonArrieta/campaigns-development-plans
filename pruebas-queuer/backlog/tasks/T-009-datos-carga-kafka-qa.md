---
id: T-009
aliases: [T-009]
title: "Datos de prueba y destino Kafka en QA para la carga"
status: done
priority: P1
epic: E-modular
estimate: M
depends_on: []
type: task
created: 2026-10-22
---

# T-009 — Datos de prueba y destino Kafka en QA para la carga

## Objetivo
Cada `202` de la carga es un mensaje real en los tópicos que consume `platform_campaigns_ms` en QA. Esta tarjeta define con qué datos se genera esa carga:
- el `applicationIdentifier` y los `userIdentifier`;
- a qué tópicos y con qué secreto se publica;
- qué hace el consumidor con esos mensajes.

El objetivo es que la carga sea segura y que los mensajes se puedan verificar después en [[T-013-validacion-kafka-modular|T-013]].

La prueba modular de `campaigns_ms` (`Back/Modular/campaigns_ms/SC_campaigns.jmx`) ya publica directamente en esos tópicos con estos valores, que sirven de punto de partida:

| Dato | Valor en `SC_campaigns.jmx` |
|---|---|
| `testAppId` | `performance_test` |
| Chatter / `userIdentifier` | `57${__Random(0000000000,9999999999)}` |
| Tópico de campañas | `thirdpartycampaignexecution.initiatecampaignv1` |
| Tópico de notificaciones | `thirdpartycampaignmanagement.executenotificationv1` |
| Secreto Kafka | `secretKafka` (por defecto un secreto `...-qa-secret-operative-eda-...`) |

## Documentación relacionada
- [Enrutamiento por segmento](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)
- [Credenciales](../../docs/publicacion-kafka.md#2-credenciales-kafkasecretprovider)
- [[T-003-datos-prueba-kafka-dev|T-003]]: misma definición para `dev`.

## Archivos a crear/modificar
- `docs/pruebas.md`, sección [Pruebas modulares](../../docs/pruebas.md#pruebas-modulares-jmeter): tabla de datos de QA.

## Tareas
- [x] Leer (sin modificar) el item de configuración de segmentos en DynamoDB de QA. Confirmar en qué segmento está `performance_test` y que su bloque `kafka` trae `campaigns`, `notifications` y `secret_campaigns`.
- [ ] Confirmar que los tópicos de ese bloque son los mismos que consume `platform_campaigns_ms` en QA.
- [ ] Confirmar que la identidad AWS de las pruebas modulares puede leer el secreto `secret_campaigns`, porque lo necesita [[T-013-validacion-kafka-modular|T-013]]. Anotar solo si tiene acceso, nunca el valor.
- [x] Con el equipo de `platform_campaigns_ms`, confirmar qué hace el consumidor con `performance_test` en QA: si entrega al canal, la carga no puede llegar a números reales. Si hace falta, usar un `userIdentifier` fijo ficticio en lugar del aleatorio.
- [x] Definir el `appId` de la carga y el criterio de `userIdentifier`, y registrarlos en `docs/pruebas.md`.

## Criterios de aceptación
- [x] Hay un `appId` de QA que resuelve a un segmento con tópicos y secreto, comprobado con `202` en una petición manual.
- [ ] Está documentado el efecto aguas abajo de la carga y aceptado por el equipo consumidor.
- [x] No queda ningún secreto ni valor sensible en el vault.

## Verificación
```bash
# Una sola peticion manual con el appId elegido (TOKEN, HOST y PFX como en T-008)
ID="qmod-check-$(date +%s)"
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/campaigns" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"metadata":{"Id":"'"$ID"'","Source":"performance:queuer-modular","SpecVersion":"1.0.2","Type":"initiatecampaign","DataContentType":"application/json","DataSchema":"https://schema-registry.com","Time":"2026-10-22T00:00:00Z"},"data":{"applicationIdentifier":"performance_test","sourceChannel":"WhatsApp","userIdentifier":"573000000000","campaign":{"identifier":"cmp-qmod","notification":{"identifier":"notif-qmod","dataTime":"2026-10-22 00:00:00"}}}}'
# Esperado: {"status":"accepted",...} -> 202
```

## Notas
- Leer DynamoDB y Secrets Manager en QA es solo lectura. Cualquier cambio en la configuración de segmentos o en secretos requiere confirmación del usuario.
- 2026-10-28 — Lectura (solo lectura, rol SSO `FullStackQARole`, cuenta de QA) del item de segmentos en DynamoDB de QA. La clave real no es la de `docs/publicacion-kafka.md`: `component` = `platform-segments-destinies-config-map-v1` y `config_name` = `-config.json` (sale del default `${CONFIG-TARGET-NAME:-config.json}` de Spring, que deja el `-` inicial). `performance_test` (y `others-test`) están en el segmento `others`, cuyo bloque `kafka` trae `campaigns` = `thirdpartycampaignexecution.initiatecampaignv1`, `notifications` = `thirdpartycampaignmanagement.executenotificationv1` y `secret_campaigns` con valor. Coinciden con los de `SC_campaigns.jmx`. Hay un séptimo segmento `pilots` que `queuer_ms` no modela; `prototype` y `pilots` tienen `campaigns`/`notifications` en `PENDIENTE`.
- 2026-10-28 — `secretsmanager:GetSecretValue` sobre `secret_campaigns` con el rol `FullStackQARole` → `AccessDeniedException`. Falta comprobarlo con la identidad que usan las pruebas modulares (la de [[T-013-validacion-kafka-modular|T-013]]).
- 2026-10-28 — `platform_campaigns_ms` toma sus tópicos de las variables `#{<segment>-batch-campaign-kafka-topic-name}#` / `#{<segment>-online-campaign-kafka-topic-name}#` de la library del release (`platform_campaigns_Conf/platform-campaigns.yaml`); el repo no trae los valores de QA, así que la coincidencia con los tópicos `thirdparty*` queda sin confirmar. El consumidor tiene `WHATSAPP-OUT-TOPIC`, `WEBCHAT-OUT-TOPIC` y `TEAMS-OUT-TOPIC`: reenvía al canal, por lo que el `userIdentifier` aleatorio `57XXXXXXXXXX` de `SC_campaigns.jmx` puede corresponder a números reales. Falta la confirmación del equipo de `platform_campaigns_ms`.
- 2026-10-28 — El usuario indica que en QA el consumidor entrega en `fakechannel`, así que el `userIdentifier` puede ser aleatorio (`57` + 10 dígitos). Con su aprobación se publicó **una** campaña en QA: `metadata.Id` `qmod-check-1793201320`, `applicationIdentifier` `performance_test`, `userIdentifier` aleatorio → `202 {"message":"Campaign event accepted for Kafka publication","status":"accepted"}` en 2,4 s. Datos registrados en `docs/pruebas.md` (Pruebas modulares → Datos de prueba en QA).
- 2026-10-28 — Cerrada como `done` con la verificación funcional, por decisión del usuario (igual que [[T-008-exposicion-rutas-qa|T-008]]). Quedan sin confirmar y sin marcar: que `platform_campaigns_ms` en QA consume los tópicos `thirdparty*` (sus valores viven en la library del release), que la identidad de las pruebas modulares puede leer `secret_campaigns` (necesario para [[T-013-validacion-kafka-modular|T-013]]) y la aceptación explícita del equipo consumidor.
