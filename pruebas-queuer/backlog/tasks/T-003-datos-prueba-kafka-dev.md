---
id: T-003
aliases: [T-003]
title: "Definir y verificar datos de prueba Kafka en dev (appId, segmento, secreto, tópicos)"
status: todo
priority: P1
epic: E-entorno
estimate: M
depends_on: []
type: task
created: 2026-10-21
---

# T-003 — Definir y verificar datos de prueba Kafka en `dev`

## Objetivo
Los escenarios `202` publican de verdad en Kafka y el consumidor (`platform_campaigns_ms`) procesa el evento: una campaña llega al motor conversacional y una notificación al adaptador del canal. Por eso hace falta un `applicationIdentifier` **de prueba** cuyo segmento tenga el bloque `kafka` completo en `dev` y cuyo procesamiento aguas abajo no entregue mensajes a usuarios reales, más un `userIdentifier` ficticio.

También se necesita un `appId` que **no** exista en ningún segmento para el escenario `422`.

## Documentación relacionada
- [Enrutamiento por segmento y formato de la configuración](../../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)
- [Formato del secreto](../../docs/publicacion-kafka.md#2-credenciales-kafkasecretprovider)
- [Observación 7: segmentos no modelados](../../docs/observaciones.md#7-segmentos-no-modelados)

## Archivos a crear/modificar
- `pruebas-queuer/docs/pruebas.md` (sección "Datos de prueba en dev")
- Notas de esta tarjeta con los valores elegidos (sin secretos).

## Tareas
- [ ] Leer el item de segmentos y destinos de `dev` y listar qué segmentos tienen `kafka.campaigns`, `kafka.notifications` y `kafka.secret_campaigns`.
- [ ] Elegir `kafkaAppId` de prueba en uno de esos segmentos. Candidato: `others-test` (lo usa `campaigns-cli` como `CLI_TEST_APP_ID`); confirmar con el usuario. El segmento debe ser uno de `clients`, `employees`, `client-countries`, `employee-countries`, `others`, `prototype`.
- [ ] Confirmar que el secreto `secret_campaigns` existe y trae `username`, `password`, `bootstrapserver` (sin imprimir valores).
- [ ] Confirmar con el usuario qué hace el consumidor con eventos de ese `appId` y que el `userIdentifier` ficticio (`573000000000`) no recibe nada real.
- [ ] Elegir el `appId` inexistente para `422`: `queuer-acceptance-sin-segmento` (verificar que no está en ninguna lista).
- [ ] Hacer una publicación manual de campaña y otra de notificación con curl y comprobar `202`.
- [ ] Documentar los valores en `docs/pruebas.md`.
- [ ] Si falta configurar el segmento o el secreto, **detenerse**: modificar el item de DynamoDB o crear secretos requiere confirmación del usuario.

## Criterios de aceptación
- [ ] `kafkaAppId` definido, en un segmento con los tres valores Kafka, y aprobado por el usuario.
- [ ] `POST /api/v1/campaigns` y `POST /api/v1/notifications` con ese `appId` responden `202` en `dev`.
- [ ] Con `queuer-acceptance-sin-segmento` responden `422 No existe segmento configurado para applicationIdentifier: queuer-acceptance-sin-segmento`.
- [ ] `docs/pruebas.md` tiene la sección "Datos de prueba en dev" con los valores (sin secretos).

## Verificación
```bash
# Configuracion de segmentos (tabla/llaves: variables CONFIG_REPOSITORY_NAME, SEGMENTS-DESTINIES-CONFIG-IDENTIFIER, CONFIG-TARGET-NAME del release)
aws dynamodb get-item --table-name nu0284001-artemis-chatbots-platform-dev-config-data \
  --key "{\"component\":{\"S\":\"platform-segments-destinies-config-map-v1\"},\"config_name\":{\"S\":\"$CONFIG_TARGET_NAME\"}}" \
  --query 'Item.data.S' --output text \
  | jq '{segments, kafka: (.segments_destinies | map_values(.kafka | {campaigns, notifications, secret_campaigns}))}'

# El secreto existe y tiene las llaves esperadas (solo nombres de llaves)
aws secretsmanager get-secret-value --secret-id "$SECRET_CAMPAIGNS" --query SecretString --output text | jq 'keys'

# Publicacion manual (URL_EXT y TOKEN como en T-002)
curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT/api/v1/campaigns" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d @campaign.json        # 202 (campaign.json de docs/pruebas.md con el kafkaAppId)
curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT/api/v1/notifications" -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d @notification.json    # 202
```

## Notas
- Cada ejecución de la suite de aceptación publicará 2 campañas y 2 notificaciones en `dev`. Acordarlo con el equipo dueño de los tópicos.
