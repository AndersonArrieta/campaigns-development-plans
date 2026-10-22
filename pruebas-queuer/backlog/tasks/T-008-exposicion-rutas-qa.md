---
id: T-008
aliases: [T-008]
title: "Verificar exposición de /api/v1/* en QA para las pruebas modulares"
status: todo
priority: P1
epic: E-modular
estimate: S
depends_on: []
type: task
created: 2026-10-22
---

# T-008 — Verificar exposición de `/api/v1/*` en QA para las pruebas modulares

## Objetivo
Las pruebas modulares corren en **QA**, no en `dev`. Los valores por defecto de `SC_queuer.jmx` son `informacion-ext-qa.apps.ambientesbc.com`, `/artemis/platform/queuer/testing/queuer` y el Cognito `chatbots-artemis-qa`. Antes de escribir los grupos de carga hay que confirmar tres cosas:
- que la rama `feature/7931497-queuer-ms-kafka-rest-proxy` está desplegada en QA;
- que el VirtualService externo de QA enruta `/api/v1/campaigns` y `/api/v1/notifications`;
- cuál es el `path` completo que usará JMeter.

Es el equivalente en QA de [[T-002-verificar-exposicion-rutas|T-002]].

## Documentación relacionada
- [Endpoints nuevos](../../docs/README.md#endpoints-nuevos)
- [[T-002-verificar-exposicion-rutas|T-002]]: mismo procedimiento en `dev`.

## Archivos a crear/modificar
- Ninguno si la exposición ya es correcta.
- Si no lo es: variables `vs-external-match` / `vs-external-rewrite` de la library de QA del release de `queuer_ms`, previa confirmación del usuario.

## Tareas
- [ ] Confirmar qué versión de imagen de `queuer_ms` está desplegada en QA y si incluye la rama de los endpoints Kafka. Si no la incluye, **detenerse** y pedir al usuario el despliegue: es una acción sobre el ambiente.
- [ ] Obtener `match.uri.prefix` y `rewrite.uri` del VirtualService externo del queuer en QA y deducir el path de las rutas nuevas (hipótesis: `/artemis/platform/queuer/testing/api/v1/campaigns`).
- [ ] Obtener un token de Cognito QA con el `clientId` de las pruebas modulares (el mismo que usa `GH_setUp`).
- [ ] Llamar a las dos rutas con un body sin `metadata`. Así el `Handler` responde `400` sin publicar en Kafka.

## Criterios de aceptación
- [ ] Las dos rutas responden `400` con `{"error":"El objeto 'metadata' es obligatorio"}` en QA, con token válido.
- [ ] En `## Notas` quedan anotados el host, el `pathCampaigns` y el `pathNotifications` efectivos, y la versión de imagen desplegada.

## Verificación
```bash
# Desde una máquina con acceso al host externo de QA. TOKEN = access_token de Cognito QA (client_credentials)
HOST=https://informacion-ext-qa.apps.ambientesbc.com
PFX=/artemis/platform/queuer/testing   # ajustar al prefijo real
BODY_C='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","campaign":{"identifier":"x","notification":{"identifier":"x","dataTime":"x"}}}}'
BODY_N='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","notification":{"identifier":"x","dataTime":"x","message":"x"}}}'
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/api/v1/campaigns" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$BODY_C"
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/api/v1/notifications" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$BODY_N"
# Esperado en ambos: {"error":"El objeto 'metadata' es obligatorio"} -> 400
```

## Notas
- Un `404` indica que el VirtualService no enruta las rutas o que la imagen desplegada no las trae. No es un fallo de la prueba.
