---
id: T-009
aliases: [T-009]
title: "Datos de prueba y destino Kafka en QA para la carga"
status: todo
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
- [ ] Leer (sin modificar) el item de configuración de segmentos en DynamoDB de QA. Confirmar en qué segmento está `performance_test` y que su bloque `kafka` trae `campaigns`, `notifications` y `secret_campaigns`.
- [ ] Confirmar que los tópicos de ese bloque son los mismos que consume `platform_campaigns_ms` en QA.
- [ ] Confirmar que la identidad AWS de las pruebas modulares puede leer el secreto `secret_campaigns`, porque lo necesita [[T-013-validacion-kafka-modular|T-013]]. Anotar solo si tiene acceso, nunca el valor.
- [ ] Con el equipo de `platform_campaigns_ms`, confirmar qué hace el consumidor con `performance_test` en QA: si entrega al canal, la carga no puede llegar a números reales. Si hace falta, usar un `userIdentifier` fijo ficticio en lugar del aleatorio.
- [ ] Definir el `appId` de la carga y el criterio de `userIdentifier`, y registrarlos en `docs/pruebas.md`.

## Criterios de aceptación
- [ ] Hay un `appId` de QA que resuelve a un segmento con tópicos y secreto, comprobado con `202` en una petición manual.
- [ ] Está documentado el efecto aguas abajo de la carga y aceptado por el equipo consumidor.
- [ ] No queda ningún secreto ni valor sensible en el vault.

## Verificación
```bash
# Una sola peticion manual con el appId elegido (TOKEN, HOST y PFX como en T-008)
ID="qmod-check-$(date +%s)"
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/api/v1/campaigns" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" \
  -d '{"metadata":{"Id":"'"$ID"'","Source":"performance:queuer-modular","SpecVersion":"1.0.2","Type":"initiatecampaign","DataContentType":"application/json","DataSchema":"https://schema-registry.com","Time":"2026-10-22T00:00:00Z"},"data":{"applicationIdentifier":"performance_test","sourceChannel":"WhatsApp","userIdentifier":"573000000000","campaign":{"identifier":"cmp-qmod","notification":{"identifier":"notif-qmod","dataTime":"2026-10-22 00:00:00"}}}}'
# Esperado: {"status":"accepted",...} -> 202
```

## Notas
- Leer DynamoDB y Secrets Manager en QA es solo lectura. Cualquier cambio en la configuración de segmentos o en secretos requiere confirmación del usuario.
