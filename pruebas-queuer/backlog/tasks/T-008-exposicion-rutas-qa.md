---
id: T-008
aliases: [T-008]
title: "Verificar exposición de /campaigns y /notifications en QA para las pruebas modulares"
status: done
priority: P1
epic: E-modular
estimate: S
depends_on: []
type: task
created: 2026-10-22
---

# T-008 — Verificar exposición de `/campaigns` y `/notifications` en QA para las pruebas modulares

## Objetivo
Las pruebas modulares corren en **QA**, no en `dev`. Los valores por defecto de `SC_queuer.jmx` son `informacion-ext-qa.apps.ambientesbc.com`, `/artemis/platform/queuer/testing/queuer` y el Cognito `chatbots-artemis-qa`. Antes de escribir los grupos de carga hay que confirmar tres cosas:
- que la rama `feature/7931497-queuer-ms-kafka-rest-proxy` está desplegada en QA;
- que el VirtualService externo de QA enruta `/campaigns` y `/notifications`;
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
- [ ] Obtener `match.uri.prefix` y `rewrite.uri` del VirtualService externo del queuer en QA y deducir el path de las rutas nuevas (hipótesis: `/artemis/platform/queuer/testing/campaigns`).
- [x] Obtener un token de Cognito QA con el `clientId` de las pruebas modulares (el mismo que usa `GH_setUp`).
- [x] Llamar a las dos rutas con un body sin `metadata`. Así el `Handler` responde `400` sin publicar en Kafka.

## Criterios de aceptación
- [x] Las dos rutas responden `400` con `{"error":"El objeto 'metadata' es obligatorio"}` en QA, con token válido.
- [ ] En `## Notas` quedan anotados el host, el `pathCampaigns` y el `pathNotifications` efectivos, y la versión de imagen desplegada.

## Verificación
```bash
# Desde una máquina con acceso al host externo de QA. TOKEN = access_token de Cognito QA (client_credentials)
HOST=https://informacion-ext-qa.apps.ambientesbc.com
PFX=/artemis/platform/queuer/testing   # ajustar al prefijo real
BODY_C='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","campaign":{"identifier":"x","notification":{"identifier":"x","dataTime":"x"}}}}'
BODY_N='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","notification":{"identifier":"x","dataTime":"x","message":"x"}}}'
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/campaigns" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$BODY_C"
curl -s -w ' -> %{http_code}\n' -X POST "$HOST$PFX/notifications" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$BODY_N"
# Esperado en ambos: {"error":"El objeto 'metadata' es obligatorio"} -> 400
```

## Notas
- Un `404` indica que el VirtualService no enruta las rutas o que la imagen desplegada no las trae. No es un fallo de la prueba.
- 2026-10-28 — Sondeo sin token contra `https://informacion-ext-qa.apps.ambientesbc.com` (`POST` con `{}`, sin publicar): con el prefijo `/artemis/platform/queuer/testing` todas las rutas (`/queuer`, `/campaigns`, `/notifications`, `/api/v1/campaigns`) responden `404`, así que el `path` por defecto de `SC_queuer.jmx` no sirve en QA. Con `/artemis/platform/queuer/v1`, `/queuer`, `/api/v1/campaigns`, `/api/v1/notifications` y una ruta inexistente responden `403 RBAC: access denied`: el VirtualService captura el prefijo, pero la AuthorizationPolicy corta antes del `Handler`. Falta un token de Cognito QA para confirmar las rutas. No hay contexto `kubectl` de QA (solo `eks-informacion-dev` y `eks-informacion-pdn`).
- 2026-10-28 — Con token de Cognito QA (`client_credentials`, `chatbots-artemis-qa`), host `https://informacion-ext-qa.apps.ambientesbc.com`: `pathCampaigns` = `/artemis/platform/queuer/v1/campaigns` y `pathNotifications` = `/artemis/platform/queuer/v1/notifications` responden `400 {"error":"El objeto 'metadata' es obligatorio"}`. Las variantes `/api/v1/campaigns` y `/api/v1/notifications` responden `404` del propio servicio (`"path":"/api/v1/campaigns"`): la imagen en QA ya trae las rutas sin el prefijo `/api/v1` (cambio de [[T-021-quitar-prefijo-api-v1|T-021]]). `/queuer` responde `400 Identificador es obligatorio`. El path para JMeter (`V_path`) es `/artemis/platform/queuer/v1/queuer`, no el valor por defecto `/testing/queuer`.
- Inferido, sin confirmar con `kubectl`: `vs-external-match` = `/artemis/platform/queuer/v1` y `vs-external-rewrite` = raíz del servicio, porque el servicio recibe `/api/v1/campaigns` cuando se llama `<prefijo>/api/v1/campaigns`. No hace falta cambiar variables del release.
- Pendiente: versión de imagen desplegada en QA. No hay contexto `kubectl` de QA.
- 2026-10-28 — Cerrada como `done` con la verificación funcional, por decisión del usuario (igual que [[T-002-verificar-exposicion-rutas|T-002]]). Sin contexto `kubectl` de QA quedan sin confirmar la versión de imagen desplegada y los valores reales de `match`/`rewrite`; esas tareas y ese criterio quedan sin marcar.
