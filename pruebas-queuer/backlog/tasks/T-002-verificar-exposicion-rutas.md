---
id: T-002
aliases: [T-002]
title: "Verificar exposición de /api/v1/* por VirtualService y Cognito en dev"
status: todo
priority: P1
epic: E-entorno
estimate: S
depends_on: []
type: task
created: 2026-10-21
---

# T-002 — Verificar exposición de `/api/v1/*` por VirtualService y Cognito en `dev`

## Objetivo
Confirmar que las rutas nuevas son alcanzables desde el host externo con un JWT válido de Cognito. Los VirtualService de `queuer_ms` usan `match.uri.prefix: #{vs-external-match}#` con `rewrite: #{vs-external-rewrite}#`: si el prefijo o el rewrite apuntan a `/queuer` y no a la raíz del servicio, `/api/v1/campaigns` y `/api/v1/notifications` no llegan al pod. La `AuthorizationPolicy` (receta de tres reglas) exige JWT para todo salvo health interno, lo que aplica igual a las rutas nuevas.

Sin esta confirmación los escenarios de [[T-004-aceptacion-campaigns|T-004]], [[T-005-aceptacion-notifications|T-005]] y [[T-006-humo-endpoints-kafka|T-006]] fallarían con `404` por infraestructura, no por la aplicación.

## Documentación relacionada
- [Endpoints nuevos](../../docs/README.md#endpoints-nuevos)
- Pruebas previas de la receta Cognito: `campaigns-development-plans/queuer-cognito-recipe-test/README.md`

## Archivos a crear/modificar
- Ninguno en el repo si la exposición ya es correcta.
- Si no lo es: variables `vs-external-match` / `vs-external-rewrite` (e internas) de la library del release, o `queuer_ms/deployment/k8s/virtualservice-external.yaml` y `virtualservice-internal.yaml`.

## Tareas
- [ ] Desplegar en `dev` la rama `feature/7931497-queuer-ms-kafka-rest-proxy` (o confirmar que ya está desplegada) y anotar la versión de imagen.
- [ ] Leer `match` y `rewrite` de los VirtualService del queuer en `dev`.
- [ ] Probar con curl `POST /api/v1/campaigns` y `POST /api/v1/notifications` con token válido y un body sin `metadata` (no publica en Kafka).
- [ ] Probar las mismas rutas sin token y con token inválido.
- [ ] Si el VirtualService no enruta `/api/v1/*`, **detenerse** y pedir al usuario el cambio de variables del release (acción con efecto en el ambiente).

## Criterios de aceptación
- [ ] Con token válido, ambas rutas responden `400` con `{"error":"El objeto 'metadata' es obligatorio"}` (la petición llegó al `Handler`).
- [ ] Sin token responden `403 RBAC: access denied`; con token inválido `401`.
- [ ] Anotados en las notas de esta tarjeta el `vs-external-match` y `vs-external-rewrite` efectivos y la `baseUrl` resultante.

## Verificación
```bash
kubectl get virtualservice -n artemis-dev | grep queuer
VS=$(kubectl get virtualservice -n artemis-dev -o name | grep queuer | grep external-vs)
kubectl get "$VS" -n artemis-dev \
  -o jsonpath='{.spec.http[*].match[*].uri.prefix}{"  ->  "}{.spec.http[*].rewrite.uri}{"\n"}'

source /mnt/c/Users/AndersonElitArrietaR/OneDrive\ -\ FINAIPRO\ TECHNOLOGIES\ SAS/Documentos/campaigns-development-plans/queuer-cognito-recipe-test/config.env
URL_EXT="$SCHEME://$GW_EXT$PREFIX_EXT"
TOKEN=$(curl -s -X POST "${COGNITO_URL%/}/oauth2/token" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=client_credentials --data-urlencode client_id="$CLIENT_ID" \
  --data-urlencode client_secret="$CLIENT_SECRET" | jq -r .access_token)

# Body sin "metadata" y con "data" completo: provoca una sola violacion y no publica en Kafka
BODY_C='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","campaign":{"identifier":"x","notification":{"identifier":"x","dataTime":"x"}}}}'
BODY_N='{"data":{"applicationIdentifier":"x","sourceChannel":"x","userIdentifier":"x","notification":{"identifier":"x","dataTime":"x","message":"x"}}}'

for pair in "/api/v1/campaigns|$BODY_C" "/api/v1/notifications|$BODY_N"; do
  p="${pair%%|*}"; b="${pair#*|}"
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT$p" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -d "$b"    # 400 metadata
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT$p" -H 'Content-Type: application/json' -H "Authorization: Bearer invalido" -d "$b"  # 401
  curl -s -w ' -> %{http_code}\n' -X POST "$URL_EXT$p" -H 'Content-Type: application/json' -d "$b"                                   # 403
done
```

## Notas
- Los bodies no incluyen `metadata` a propósito: el `Handler` corta en la validación y no se publica nada en Kafka.
