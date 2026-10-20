# Pruebas de la receta de Cognito – queuer_ms

Instructivo para validar la `AuthorizationPolicy` de `queuer_ms/deployment/k8s/cognito.yaml`
(commit `d8ee99d41`, rama `feature/7960847_update_cognito_recipe`).

## 1. Qué se valida

| Regla | Permite sin JWT | Condición |
|---|---|---|
| 1 | Sí | La petición viene de un namespace en `jwt-allowed-namespaces` |
| 2 | Sí | La ruta termina en `/health` **y** el `Host` es `gateway-host-internal` |
| 3 | No | Todo lo demás exige un JWT válido de Cognito |

La variable `jwt-allowed-paths` ya no se usa en este manifiesto.

Las pruebas se dividen en dos partes:

| Parte | Dónde se ejecuta | Cómo |
|---|---|---|
| Host externo | Tu máquina (VPN) | `test-queuer-cognito.sh` (secciones 3 a 5) |
| Host interno y regla 1 | Dentro del pod del queuer | Comandos manuales (sección 6) |

El host interno no se puede alcanzar desde la VPN corporativa, por eso esos escenarios se ejecutan desde dentro del clúster.

## 2. Archivos

| Archivo | Uso |
|---|---|
| `test-queuer-cognito.sh` | Script con los casos del host externo y resumen PASS/FAIL |
| `config.env.example` | Plantilla de configuración |
| `config.env` | Tu configuración real; la creas tú. Está en `.gitignore` porque contiene el secret |

### Endpoints del queuer

El microservicio no tiene base path ni context path; todos sus endpoints cuelgan de la raíz del pod:

| Método | Path en el pod | Uso |
|---|---|---|
| `POST` | `/queuer` | Único endpoint de negocio. Despacha según `operation` (hoy solo `VariableSetter`) |
| `GET` | `/actuator/health` | Estado general |
| `GET` | `/actuator/health/liveness` y `/actuator/health/readiness` | Probes |
| `GET` | `/actuator/prometheus` | Métricas |

### Body de prueba

En todos los casos se usa `{"operation":"PruebaCognito"}`. Esa operación no existe, así que la app responde
`400 "Operacion no soportada"` **sin publicar nada en RabbitMQ**. Un 400 con ese texto
significa que Istio dejó pasar la petición.

## 3. Requisitos

- Bash: Git Bash o WSL en Windows.
- `curl`. `jq` es opcional; si está instalado, el script formatea las respuestas JSON.
- VPN conectada.
- Para la sección 6: `kubectl` autenticado contra el EKS del ambiente, con permiso de `exec` en el namespace del queuer.

## 4. Configuración

### Paso 1 – Verificar que la receta nueva está desplegada

```bash
kubectl get authorizationpolicy -n <namespace> -o yaml | grep -A30 "rules:"
```

Deben aparecer las tres reglas y **no** debe aparecer `jwt-allowed-paths`.

### Paso 2 – Conseguir los valores

| Variable | Nombre en la library del release | Se usa en |
|---|---|---|
| `GW_EXT` | `gateway-host-external` | Script |
| `PREFIX_EXT` | `vs-external-match` | Script |
| `GW_INT` | `gateway-host-internal` | Sección 6 |
| `PREFIX_INT` | `vs-internal-match` | Sección 6 |

También se pueden leer del clúster:

```bash
kubectl get virtualservice -n <namespace> | grep queuer
kubectl get virtualservice <nombre-vs> -n <namespace> \
  -o jsonpath='{.spec.hosts}{"\n"}{.spec.http[0].match[0].uri.prefix}{"\n"}{.spec.http[0].rewrite.uri}{"\n"}'
```

Las credenciales de Cognito son las mismas que usa `Platform_test`:
`COGNITO_URL` (`-DcognitoEndpoint`), `CLIENT_ID` (`-DclientId`) y `CLIENT_SECRET` (`-DclientSecret`).

> La política se evalúa en el sidecar, **después** del `rewrite` del VirtualService. Si el rewrite cambia la
> ruta, ajusta `QUEUER_PATH` y `HEALTH_PATH` para que el path final en el pod sea `/queuer` y `/actuator/health`.

### Paso 3 – Crear `config.env`

```bash
cd "/c/Users/AndersonElitArrietaR/OneDrive - FINAIPRO TECHNOLOGIES SAS/Documentos/campaigns-development-plans/queuer-cognito-recipe-test"
cp config.env.example config.env
# editar config.env con los valores del paso 2
```

En WSL, la ruta empieza por `/mnt/c/...` en lugar de `/c/...`.

## 5. Ejecutar el script (host externo)

```bash
chmod +x test-queuer-cognito.sh
./test-queuer-cognito.sh 2>&1 | tee evidencia-externo-$(date +%Y%m%d-%H%M).log
```

Por cada caso el script imprime el HTTP status, el response body completo y PASS/FAIL. Al final muestra un resumen.
Termina con código `0` si todo pasa y `1` si algún caso falla.

| # | Caso | Esperado | Qué demuestra |
|---|---|---|---|
| 0 | Token de Cognito (`client_credentials`) | token | Credenciales OK |
| 3.1 | `POST /queuer` sin token | 403 `RBAC: access denied` | La regla 3 bloquea sin JWT |
| 3.2 | `POST /queuer` con token inválido | 401 `Jwt ...` | La RequestAuthentication rechaza tokens inválidos |
| 3.3 | `POST /queuer` con token válido | 400 `Operacion no soportada` | La regla 3 permite con JWT |
| 2.2 | `GET /actuator/health` sin token | 403 `RBAC: access denied` | Health no queda abierto por el host externo |
| 2.4 | `GET /actuator/health` con token válido | 200 `UP` | Con JWT, la regla 3 aplica también a health |

## 6. Escenarios de host interno y regla 1 (dentro del pod)

### 6.1 Qué valida cada tipo de llamada desde el pod

| Llamada desde el pod | ¿Pasa por la política? | Uso |
|---|---|---|
| `http://localhost:<port>/...` | **No.** El tráfico a localhost no pasa por el sidecar | No sirve como evidencia |
| `https://<GW_INT><PREFIX_INT>/...` | **Sí.** Sale al ingress gateway y vuelve al queuer por el VirtualService interno | Casos 2.1, 2.3, 3.4 y 3.5 |
| `http://<servicio>.<namespace>.svc.cluster.local:<port>/queuer` | **Sí**, con identidad del namespace del queuer (mTLS) | Caso 1.1 |

Cuando la llamada va por el host interno, el queuer la recibe desde el ingress gateway, no desde su propio pod.
Por eso la regla 1 no interfiere con esos casos: la prueba 3.1 dio 403, así que el namespace del gateway no está permitido.

### 6.2 Generar el token (en tu máquina)

El script solo muestra el token truncado. Genera uno completo y cópialo:

```bash
source config.env
curl -s -X POST "${COGNITO_URL%/}/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode "client_id=$CLIENT_ID" \
  --data-urlencode "client_secret=$CLIENT_SECRET" | sed -nE 's/.*"access_token":"([^"]+)".*/\1/p'
```

El token de `client_credentials` dura poco (por defecto, 1 hora); si recibes 401 en 3.4, genera otro.

### 6.3 Entrar al pod

```bash
kubectl get pods -n <namespace> | grep queuer
kubectl get pod <pod-queuer> -n <namespace> -o jsonpath='{.spec.containers[*].name}{"\n"}'   # nombre del contenedor

kubectl exec -it -n <namespace> <pod-queuer> -c <contenedor-queuer> -- sh
command -v curl || echo "sin curl"
```

Si el contenedor de la app no trae `curl`, usa el contenedor del sidecar:

```bash
kubectl exec -it -n <namespace> <pod-queuer> -c istio-proxy -- bash
```

> Desde `istio-proxy` las llamadas salen sin pasar por el sidecar (sin mTLS). Para los casos del host interno
> (6.4) no importa. El caso 1.1 (6.5) **sí** debe ejecutarse desde el contenedor de la app.

### 6.4 Casos del host interno

Pega esto dentro del pod, reemplazando los valores entre `< >`:

```sh
URL_INT="https://<GW_INT><PREFIX_INT>"
TOKEN="<token-completo>"
BODY='{"operation":"PruebaCognito"}'
CURL="curl -s --max-time 20"        # agrega -k si hay error de certificado

probar() {
  id="$1"; desc="$2"; shift 2
  echo
  echo "== [$id] $desc"
  $CURL -w '\nHTTP status: %{http_code}\n' "$@"
}

probar 2.1 "Host interno, health, sin token -> esperado 200 UP" \
  "$URL_INT/actuator/health"

probar 2.3 "Host interno, health/liveness, sin token -> esperado 403" \
  "$URL_INT/actuator/health/liveness"

probar 3.4 "Host interno, /queuer, token valido -> esperado 400 Operacion no soportada" \
  -X POST "$URL_INT/queuer" -H "Content-Type: application/json" -H "Accept: application/json" \
  -H "Authorization: Bearer $TOKEN" -d "$BODY"

probar 3.5 "Host interno, /queuer, sin token -> esperado 403 (antes podia pasar)" \
  -X POST "$URL_INT/queuer" -H "Content-Type: application/json" -H "Accept: application/json" \
  -d "$BODY"
```

| # | Caso | Esperado | Qué demuestra |
|---|---|---|---|
| 2.1 | `GET /actuator/health` sin token | 200 `UP` | La regla 2 permite health por el host interno |
| 2.3 | `GET /actuator/health/liveness` sin token | 403 `RBAC: access denied` | `*/health` solo cubre rutas que terminan en `/health` |
| 3.4 | `POST /queuer` con token válido | 400 `Operacion no soportada` | La regla 3 permite con JWT por el host interno |
| 3.5 | `POST /queuer` sin token | **403** `RBAC: access denied` | El host interno ya no abre rutas distintas de health (cambio clave frente a `jwt-allowed-paths`) |

**Si el pod no resuelve `GW_INT`** (`Could not resolve host`), entra por el ingress gateway enviando el header `Host`:

```sh
INGRESS="http://istio-ingressgateway.istio-system.svc.cluster.local:<gateway-port>"
$CURL -w '\nHTTP status: %{http_code}\n' -H "Host: <GW_INT>" "$INGRESS<PREFIX_INT>/actuator/health"
```

Aplica lo mismo a los demás casos: cambia `$URL_INT` por `$INGRESS<PREFIX_INT>` y agrega `-H "Host: <GW_INT>"`.
Si el ingress tiene otro nombre o namespace, búscalo con `kubectl get svc -A | grep ingress`.

### 6.5 Casos de la regla 1 (namespaces)

**1.1 – Namespace permitido.** Desde el **contenedor de la app** del queuer, llama directo al Service:

```sh
SVC="http://<bot-platform-distinctive>-queuer-<version>-service.<namespace>.svc.cluster.local:<service-port>"
probar 1.1 "Service directo, sin token, desde namespace del queuer -> esperado 400 si el namespace esta en jwt-allowed-namespaces" \
  -X POST "$SVC/queuer" -H "Content-Type: application/json" -H "Accept: application/json" -d "$BODY"
```

Si el namespace del queuer **no** está en `jwt-allowed-namespaces`, el esperado es 403.
Revisa la lista en la library antes de interpretar el resultado.

**1.2 – Namespace no permitido (opcional).** Repite la misma llamada desde un pod con `curl` y sidecar de Istio
en un namespace que no esté en la lista → esperado 403.

> La regla por namespace depende de mTLS. Un pod sin sidecar no envía identidad y recibe 403 aunque su namespace esté permitido.

### 6.6 Guardar la evidencia

Copia la salida de la terminal del pod. Para guardarla directo en tu máquina, puedes ejecutar los comandos sin entrar a una sesión interactiva:

```bash
kubectl exec -i -n <namespace> <pod-queuer> -c <contenedor> -- sh < casos-internos.sh \
  | tee evidencia-interno-$(date +%Y%m%d-%H%M).log
```

Para eso, guarda el bloque de la sección 6.4 (con tus valores) en `casos-internos.sh`. Como contiene el token, no lo subas al repo.

## 7. Si algo falla

| Síntoma | Causa probable |
|---|---|
| El paso 0 del script falla | `COGNITO_URL`, `CLIENT_ID` o `CLIENT_SECRET` incorrectos, o no hay conectividad con Cognito |
| HTTP `000` | Sin conectividad o VPN, host mal escrito, o error de certificado (prueba `CURL_OPTS=-k` o `-k` en el pod) |
| 404 en todos los casos | Prefijo o rewrite del VirtualService mal configurado (`PREFIX_*`, `QUEUER_PATH`, `HEALTH_PATH`) |
| 3.5 devuelve 400 | Sigue desplegada la receta anterior, o hay otra política que permite el tráfico |
| 2.1 devuelve 403 | `gateway-host-internal` no coincide con el `Host` real, o el path tras el rewrite no termina en `/health` |
| 3.3 o 3.4 devuelven 401 | Token vencido, o el `issuer`/`jwksUri` de la RequestAuthentication no corresponden al user pool del token |
| 1.1 devuelve 403 | Se ejecutó desde `istio-proxy` (sin mTLS), o el namespace no está en `jwt-allowed-namespaces` |

Comandos útiles:

```bash
# Logs del sidecar del queuer: buscar rbac_access_denied / jwt_authn
kubectl logs -n <namespace> <pod-queuer> -c istio-proxy --tail=100

# RequestAuthentication desplegada (issuer / jwksUri)
kubectl get requestauthentication -n <namespace> -o yaml
```

## 8. Regresión funcional (opcional)

`queuer_ms_test` usa el runner `IntegratorNode.java` con `integrator_node.feature` de `Platform_test`,
que entra por los adaptadores de teams, whatsapp y webchat:

```bash
cd NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test
./gradlew clean test --tests "*IntegratorNode*" \
  -DclientId=<clientId> -DclientSecret=<clientSecret> -DcognitoEndpoint=<cognitoEndpoint> \
  -DendpointTeams=<url-adapter-teams> -DappId=<appId>   # + las demás -D de tu ejecución habitual
```
