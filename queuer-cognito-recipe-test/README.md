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

## 2. Archivos

| Archivo | Uso |
|---|---|
| `test-queuer-cognito.sh` | Script que ejecuta todos los casos y muestra un resumen PASS/FAIL |
| `config.env.example` | Plantilla de configuración |
| `config.env` | Tu configuración real; la creas tú y **no se comparte** porque contiene el secret |

## 3. Requisitos

- Bash: Git Bash o WSL en Windows.
- `curl`.
- Conectividad (VPN) hacia los hosts interno y externo del gateway.
- Opcional, para la regla 1: `kubectl` autenticado contra el clúster del ambiente.

## 4. Paso a paso

### Paso 1 – Verificar que la receta nueva está desplegada

```bash
kubectl get authorizationpolicy -n <namespace> -o yaml | grep -A30 "rules:"
```

Deben aparecer las tres reglas y **no** debe aparecer `jwt-allowed-paths`.
Si sigue la versión anterior, primero despliega el release de la rama.

### Paso 2 – Conseguir los valores de configuración

En Azure DevOps, abre el release de `queuer_ms` y su librería de variables del ambiente.
Toma estos valores:

| Variable del script | Variable del release |
|---|---|
| `GW_INT` | `gateway-host-internal` |
| `GW_EXT` | `gateway-host-external` |
| `PREFIX_INT` | `vs-internal-match` |
| `PREFIX_EXT` | `vs-external-match` |

Las credenciales de Cognito son las mismas que usa `Platform_test`:
`COGNITO_URL` (`-DcognitoEndpoint`), `CLIENT_ID` (`-DclientId`) y `CLIENT_SECRET` (`-DclientSecret`).

> Revisa también `vs-internal-rewrite` y `vs-external-rewrite`. La política se evalúa en el sidecar,
> **después** del rewrite. Si el rewrite cambia la ruta, ajusta `QUEUER_PATH` y `HEALTH_PATH` para que
> el path final que llega al pod sea `/queuer` y `.../health`.

### Paso 3 – Crear `config.env`

```bash
cd "/c/Users/AndersonElitArrietaR/OneDrive - FINAIPRO TECHNOLOGIES SAS/Documentos/campaigns-development-plans/queuer-cognito-recipe-test"
cp config.env.example config.env
# editar config.env con los valores del paso 2
```

En WSL, la ruta empieza por `/mnt/c/...` en lugar de `/c/...`.

### Paso 4 – Ejecutar

```bash
chmod +x test-queuer-cognito.sh
./test-queuer-cognito.sh
```

Si el certificado del gateway no es de confianza en tu máquina, pon `CURL_OPTS=-k` en `config.env`.

Para guardar la evidencia en un archivo:

```bash
./test-queuer-cognito.sh 2>&1 | tee evidencia-$(date +%Y%m%d-%H%M).log
```

El script termina con código `0` si todo pasa y `1` si algún caso falla.

### Paso 5 (opcional) – Probar la regla 1 desde el clúster

1. Elige un pod con `curl` y sidecar de Istio en un namespace que **sí** esté en `jwt-allowed-namespaces`,
   y otro en un namespace que **no** esté.
2. En `config.env`, pon `RUN_RULE1=true` y completa `K8S_SERVICE_URL`, `ALLOWED_*` y `DENIED_*`.
3. Ejecuta de nuevo el script.

> La regla por namespace depende de mTLS. Si el pod origen no tiene sidecar,
> la identidad no se propaga y se obtendrá 403 aunque el namespace esté permitido.

## 5. Casos y resultados esperados

El body de prueba es `{"operation":"PruebaCognito"}`. Esa operación no existe, así que la app responde
`400 "Operacion no soportada"` **sin publicar nada en RabbitMQ**. Un 400 con ese texto
significa que Istio dejó pasar la petición.

| # | Host | Ruta | Token | Esperado | Qué demuestra |
|---|---|---|---|---|---|
| 0 | – | Cognito `/oauth2/token` | – | token | Credenciales OK |
| 3.1 | externo | `/queuer` | no | 403 `RBAC: access denied` | Regla 3 bloquea sin JWT |
| 3.2 | externo | `/queuer` | inválido | 401 `Jwt verification fails` | RequestAuthentication rechaza tokens inválidos |
| 3.3 | externo | `/queuer` | válido | 400 `Operacion no soportada` | Regla 3 permite con JWT |
| 3.4 | interno | `/queuer` | válido | 400 `Operacion no soportada` | Regla 3 permite con JWT |
| 3.5 | interno | `/queuer` | no | **403** | El host interno ya no abre rutas distintas de health (antes podían pasar) |
| 2.1 | interno | `/actuator/health` | no | 200 `UP` | Regla 2 permite health interno |
| 2.2 | externo | `/actuator/health` | no | 403 | Regla 2 restringe por host |
| 2.3 | interno | `/actuator/health/liveness` | no | 403 | `*/health` solo cubre rutas que terminan en `/health` |
| 2.4 | externo | `/actuator/health` | válido | 200 `UP` | Con JWT, la regla 3 aplica también a health |
| 1.1 | pod en ns permitido | `/queuer` (Service) | no | 400 `Operacion no soportada` | Regla 1 permite tráfico interno |
| 1.2 | pod en ns no permitido | `/queuer` (Service) | no | 403 | Regla 1 restringe por namespace |

## 6. Si algo falla

| Síntoma | Causa probable |
|---|---|
| El paso 0 falla | `COGNITO_URL`, `CLIENT_ID` o `CLIENT_SECRET` incorrectos, o no hay conectividad con Cognito |
| HTTP `000` | Sin conectividad o VPN, host mal escrito, o problema de certificado (prueba `CURL_OPTS=-k`) |
| 404 en todos los casos | Prefijo o rewrite del VirtualService mal configurado (`PREFIX_*`, `QUEUER_PATH`, `HEALTH_PATH`) |
| 3.5 devuelve 400 | Sigue desplegada la receta anterior o hay otra política que permite el tráfico |
| 2.1 devuelve 403 | `gateway-host-internal` no coincide con el `Host` real, o el path tras el rewrite no termina en `/health` |
| 3.3 devuelve 401 | El `issuer` o `jwksUri` de la RequestAuthentication no corresponden al user pool del token |
| 1.1 devuelve 403 | El pod origen no tiene sidecar (sin mTLS) o el namespace no está en `jwt-allowed-namespaces` |

Comandos útiles:

```bash
# Logs del sidecar del queuer: buscar rbac_access_denied / jwt_authn
kubectl logs -n <namespace> <pod-queuer> -c istio-proxy --tail=100

# RequestAuthentication desplegada (issuer / jwksUri)
kubectl get requestauthentication -n <namespace> -o yaml
```

## 7. Regresión funcional (opcional)

`queuer_ms_test` usa el runner `IntegratorNode.java` con `integrator_node.feature` de `Platform_test`,
que entra por los adaptadores de teams, whatsapp y webchat:

```bash
cd NU0284001_Artemis_Chatbots_Platform_MR_Test/Platform_test
./gradlew clean test --tests "*IntegratorNode*" \
  -DclientId=<clientId> -DclientSecret=<clientSecret> -DcognitoEndpoint=<cognitoEndpoint> \
  -DendpointTeams=<url-adapter-teams> -DappId=<appId>   # + las demás -D de tu ejecución habitual
```
