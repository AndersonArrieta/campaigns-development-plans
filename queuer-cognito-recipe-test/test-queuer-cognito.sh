#!/usr/bin/env bash
###############################################################################
# Pruebas de la receta de Cognito (AuthorizationPolicy de tres reglas)
# para queuer_ms.
#
#   Regla 1: sin JWT desde namespaces internos (jwt-allowed-namespaces)
#   Regla 2: sin JWT a */health solo desde el host interno (gateway-host-internal)
#   Regla 3: el resto requiere JWT valido de Cognito
#
# Uso:
#   ./test-queuer-cognito.sh                 # lee config.env junto al script
#   CONFIG_FILE=otro.env ./test-queuer-cognito.sh
#
# Ver README.md para el detalle de cada variable.
###############################################################################
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source <(sed 's/\r$//' "$CONFIG_FILE")
fi

# ----------------------------- Configuracion ---------------------------------
SCHEME="${SCHEME:-https}"
GW_INT="${GW_INT:-}"
GW_EXT="${GW_EXT:-}"
PREFIX_INT="${PREFIX_INT:-}"
PREFIX_EXT="${PREFIX_EXT:-}"
HEALTH_PATH="${HEALTH_PATH:-/actuator/health}"
QUEUER_PATH="${QUEUER_PATH:-/queuer}"

COGNITO_URL="${COGNITO_URL:-}"
CLIENT_ID="${CLIENT_ID:-}"
CLIENT_SECRET="${CLIENT_SECRET:-}"
TOKEN="${TOKEN:-}"

CURL_OPTS="${CURL_OPTS:-}"          # ej: "-k" si el certificado no es de confianza
CURL_TIMEOUT="${CURL_TIMEOUT:-20}"

# Regla 1 (opcional): pruebas desde pods dentro del cluster
RUN_RULE1="${RUN_RULE1:-false}"
K8S_SERVICE_URL="${K8S_SERVICE_URL:-}"       # http://<svc>.<ns>.svc.cluster.local:<port>
ALLOWED_NS="${ALLOWED_NS:-}"
ALLOWED_POD="${ALLOWED_POD:-}"
ALLOWED_CONTAINER="${ALLOWED_CONTAINER:-}"
DENIED_NS="${DENIED_NS:-}"
DENIED_POD="${DENIED_POD:-}"
DENIED_CONTAINER="${DENIED_CONTAINER:-}"

# Body inocuo: llega a la app y responde 400 sin publicar en RabbitMQ
BODY='{"operation":"PruebaCognito"}'
INVALID_TOKEN='eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcnVlYmEifQ.firmainvalida'

# ------------------------------- Utilidades ----------------------------------
if [[ -t 1 ]]; then
  GREEN=$'\e[32m'; RED=$'\e[31m'; YELLOW=$'\e[33m'; BOLD=$'\e[1m'; RESET=$'\e[0m'
else
  GREEN=''; RED=''; YELLOW=''; BOLD=''; RESET=''
fi

PASSED=0; FAILED=0; SKIPPED=0
RESULTS=()

require_vars() {
  local missing=()
  for v in "$@"; do
    [[ -z "${!v}" ]] && missing+=("$v")
  done
  if (( ${#missing[@]} > 0 )); then
    echo "${RED}Faltan variables: ${missing[*]}${RESET}"
    echo "Definelas en $CONFIG_FILE o como variables de entorno (ver README.md)."
    exit 2
  fi
}

record() {
  local status="$1" id="$2" desc="$3" detail="$4"
  case "$status" in
    PASS) PASSED=$((PASSED+1)); echo "  ${GREEN}PASS${RESET} $detail" ;;
    FAIL) FAILED=$((FAILED+1)); echo "  ${RED}FAIL${RESET} $detail" ;;
    SKIP) SKIPPED=$((SKIPPED+1)); echo "  ${YELLOW}SKIP${RESET} $detail" ;;
  esac
  RESULTS+=("$status|$id|$desc|$detail")
}

# evaluate <id> <desc> <expected_code> <expected_body_substring|""> <code> <body>
evaluate() {
  local id="$1" desc="$2" exp_code="$3" exp_body="$4" code="$5" body="$6"
  local short_body
  short_body="$(echo "$body" | tr -d '\r\n' | cut -c1-150)"
  echo "  Respuesta: HTTP $code | $short_body"
  if [[ "$code" != "$exp_code" ]]; then
    record FAIL "$id" "$desc" "esperado HTTP $exp_code, obtenido HTTP $code"
  elif [[ -n "$exp_body" && "$body" != *"$exp_body"* ]]; then
    record FAIL "$id" "$desc" "HTTP $code correcto, pero el body no contiene '$exp_body'"
  else
    record PASS "$id" "$desc" "HTTP $code${exp_body:+ y body contiene '$exp_body'}"
  fi
}

# http_case <id> <desc> <expected_code> <expected_body> <curl args...>
http_case() {
  local id="$1" desc="$2" exp_code="$3" exp_body="$4"; shift 4
  echo
  echo "${BOLD}[$id] $desc${RESET}"
  local tmp code body
  tmp="$(mktemp)"
  # shellcheck disable=SC2086
  code="$(curl -s $CURL_OPTS --max-time "$CURL_TIMEOUT" -o "$tmp" -w '%{http_code}' "$@")"
  body="$(cat "$tmp")"; rm -f "$tmp"
  evaluate "$id" "$desc" "$exp_code" "$exp_body" "$code" "$body"
}

# pod_case <id> <desc> <expected_code> <expected_body> <ns> <pod> <container>
pod_case() {
  local id="$1" desc="$2" exp_code="$3" exp_body="$4" ns="$5" pod="$6" container="$7"
  echo
  echo "${BOLD}[$id] $desc${RESET}"
  if [[ -z "$ns" || -z "$pod" ]]; then
    record SKIP "$id" "$desc" "namespace/pod no configurados"
    return
  fi
  local container_arg=()
  [[ -n "$container" ]] && container_arg=(-c "$container")
  local out code body
  out="$(kubectl exec -n "$ns" "$pod" "${container_arg[@]}" -- \
    curl -s --max-time "$CURL_TIMEOUT" -w '\n%{http_code}' -X POST "$K8S_SERVICE_URL$QUEUER_PATH" \
    -H 'Content-Type: application/json' -H 'Accept: application/json' -d "$BODY" 2>&1)"
  code="$(echo "$out" | tail -n1 | tr -d '\r')"
  body="$(echo "$out" | sed '$d')"
  evaluate "$id" "$desc" "$exp_code" "$exp_body" "$code" "$body"
}

# --------------------------------- Inicio ------------------------------------
require_vars GW_INT GW_EXT
command -v curl >/dev/null || { echo "${RED}curl no esta instalado${RESET}"; exit 2; }

URL_INT="$SCHEME://$GW_INT$PREFIX_INT"
URL_EXT="$SCHEME://$GW_EXT$PREFIX_EXT"

echo "${BOLD}== Pruebas receta Cognito - queuer_ms ==${RESET}"
echo "Host interno : $URL_INT"
echo "Host externo : $URL_EXT"
echo "Fecha        : $(date '+%Y-%m-%d %H:%M:%S')"

# ------------------------------ Token Cognito --------------------------------
echo
echo "${BOLD}[0] Obtener token de Cognito${RESET}"
if [[ -n "$TOKEN" ]]; then
  echo "  Usando TOKEN provisto por variable de entorno."
else
  require_vars COGNITO_URL CLIENT_ID CLIENT_SECRET
  TOKEN_URL="${COGNITO_URL%/}"
  [[ "$TOKEN_URL" == */oauth2/token ]] || TOKEN_URL="$TOKEN_URL/oauth2/token"
  # shellcheck disable=SC2086
  token_resp="$(curl -s $CURL_OPTS --max-time "$CURL_TIMEOUT" -X POST "$TOKEN_URL" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'grant_type=client_credentials' \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode "client_secret=$CLIENT_SECRET")"
  TOKEN="$(echo "$token_resp" | sed -nE 's/.*"access_token"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')"
fi
if [[ -z "$TOKEN" ]]; then
  echo "  ${RED}No se pudo obtener el token. Respuesta de Cognito:${RESET}"
  echo "  ${token_resp:-<vacia>}" | cut -c1-300
  exit 2
fi
echo "  ${GREEN}OK${RESET} token: ${TOKEN:0:12}... (${#TOKEN} caracteres)"

JSON_HEADERS=(-H 'Content-Type: application/json' -H 'Accept: application/json')

# ------------------------------- Regla 3 -------------------------------------
echo; echo "${BOLD}---- Regla 3: JWT obligatorio ----${RESET}"

http_case "3.1" "Host externo, /queuer, sin token -> 403" 403 "RBAC" \
  -X POST "$URL_EXT$QUEUER_PATH" "${JSON_HEADERS[@]}" -d "$BODY"

http_case "3.2" "Host externo, /queuer, token invalido -> 401" 401 "Jwt" \
  -X POST "$URL_EXT$QUEUER_PATH" "${JSON_HEADERS[@]}" -H "Authorization: Bearer $INVALID_TOKEN" -d "$BODY"

http_case "3.3" "Host externo, /queuer, token valido -> 400 de la app" 400 "Operacion no soportada" \
  -X POST "$URL_EXT$QUEUER_PATH" "${JSON_HEADERS[@]}" -H "Authorization: Bearer $TOKEN" -d "$BODY"

http_case "3.4" "Host interno, /queuer, token valido -> 400 de la app" 400 "Operacion no soportada" \
  -X POST "$URL_INT$QUEUER_PATH" "${JSON_HEADERS[@]}" -H "Authorization: Bearer $TOKEN" -d "$BODY"

http_case "3.5" "Host interno, /queuer, sin token -> 403 (antes podia pasar)" 403 "RBAC" \
  -X POST "$URL_INT$QUEUER_PATH" "${JSON_HEADERS[@]}" -d "$BODY"

# ------------------------------- Regla 2 -------------------------------------
echo; echo "${BOLD}---- Regla 2: health solo por host interno ----${RESET}"

http_case "2.1" "Host interno, health, sin token -> 200" 200 "UP" \
  "$URL_INT$HEALTH_PATH"

http_case "2.2" "Host externo, health, sin token -> 403" 403 "RBAC" \
  "$URL_EXT$HEALTH_PATH"

http_case "2.3" "Host interno, health/liveness, sin token -> 403" 403 "RBAC" \
  "$URL_INT$HEALTH_PATH/liveness"

http_case "2.4" "Host externo, health, token valido -> 200" 200 "UP" \
  -H "Authorization: Bearer $TOKEN" "$URL_EXT$HEALTH_PATH"

# ------------------------------- Regla 1 -------------------------------------
echo; echo "${BOLD}---- Regla 1: namespaces internos sin JWT ----${RESET}"
if [[ "$RUN_RULE1" == "true" ]]; then
  if ! command -v kubectl >/dev/null; then
    record SKIP "1.x" "Regla 1" "kubectl no esta instalado"
  elif [[ -z "$K8S_SERVICE_URL" ]]; then
    record SKIP "1.x" "Regla 1" "K8S_SERVICE_URL no configurada"
  else
    pod_case "1.1" "Pod en namespace permitido, sin token -> 400 de la app" 400 "Operacion no soportada" \
      "$ALLOWED_NS" "$ALLOWED_POD" "$ALLOWED_CONTAINER"
    pod_case "1.2" "Pod en namespace NO permitido, sin token -> 403" 403 "RBAC" \
      "$DENIED_NS" "$DENIED_POD" "$DENIED_CONTAINER"
  fi
else
  echo; record SKIP "1.x" "Regla 1" "RUN_RULE1=false"
fi

# -------------------------------- Resumen ------------------------------------
echo
echo "${BOLD}================== RESUMEN ==================${RESET}"
for r in "${RESULTS[@]}"; do
  IFS='|' read -r st id desc detail <<< "$r"
  case "$st" in
    PASS) color="$GREEN" ;; FAIL) color="$RED" ;; *) color="$YELLOW" ;;
  esac
  printf '%s%-4s%s %-5s %s\n' "$color" "$st" "$RESET" "$id" "$desc"
done
echo "---------------------------------------------"
echo "PASS: $PASSED   FAIL: $FAILED   SKIP: $SKIPPED"

(( FAILED == 0 ))
