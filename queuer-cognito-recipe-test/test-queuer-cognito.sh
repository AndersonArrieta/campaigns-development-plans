#!/usr/bin/env bash
###############################################################################
# Pruebas de la receta de Cognito (AuthorizationPolicy de tres reglas)
# para queuer_ms - escenarios por HOST EXTERNO.
#
#   Regla 1: sin JWT desde namespaces internos (jwt-allowed-namespaces)
#   Regla 2: sin JWT a */health solo desde el host interno (gateway-host-internal)
#   Regla 3: el resto requiere JWT valido de Cognito
#
# Los escenarios de host interno y de namespaces (regla 1) se prueban
# dentro del pod del queuer: ver README.md, seccion 6.
#
# Uso:
#   ./test-queuer-cognito.sh                 # lee config.env junto al script
#   CONFIG_FILE=otro.env ./test-queuer-cognito.sh
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
GW_EXT="${GW_EXT:-}"
PREFIX_EXT="${PREFIX_EXT:-}"
HEALTH_PATH="${HEALTH_PATH:-/actuator/health}"
QUEUER_PATH="${QUEUER_PATH:-/queuer}"

COGNITO_URL="${COGNITO_URL:-}"
CLIENT_ID="${CLIENT_ID:-}"
CLIENT_SECRET="${CLIENT_SECRET:-}"
TOKEN="${TOKEN:-}"

CURL_OPTS="${CURL_OPTS:-}"          # ej: "-k" si el certificado no es de confianza
CURL_TIMEOUT="${CURL_TIMEOUT:-20}"

# Body inocuo: llega a la app y responde 400 sin publicar en RabbitMQ
BODY='{"operation":"PruebaCognito"}'
INVALID_TOKEN='eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcnVlYmEifQ.firmainvalida'

# ------------------------------- Utilidades ----------------------------------
if [[ -t 1 ]]; then
  GREEN=$'\e[32m'; RED=$'\e[31m'; YELLOW=$'\e[33m'; BOLD=$'\e[1m'; RESET=$'\e[0m'
else
  GREEN=''; RED=''; YELLOW=''; BOLD=''; RESET=''
fi

PASSED=0; FAILED=0
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
  esac
  RESULTS+=("$status|$id|$desc|$detail")
}

# evaluate <id> <desc> <expected_code> <expected_body_substring|""> <code> <body>
evaluate() {
  local id="$1" desc="$2" exp_code="$3" exp_body="$4" code="$5" body="$6"
  echo "  HTTP status  : $code"
  echo "  Response body:"
  if [[ -z "$body" ]]; then
    echo "    <vacio>"
  elif command -v jq >/dev/null && echo "$body" | jq -e . >/dev/null 2>&1; then
    echo "$body" | jq . | sed 's/^/    /'
  else
    echo "$body" | tr -d '\r' | sed 's/^/    /'
  fi
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

# --------------------------------- Inicio ------------------------------------
require_vars GW_EXT
command -v curl >/dev/null || { echo "${RED}curl no esta instalado${RESET}"; exit 2; }

URL_EXT="$SCHEME://$GW_EXT$PREFIX_EXT"

echo "${BOLD}== Pruebas receta Cognito - queuer_ms (host externo) ==${RESET}"
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

# ------------------------------- Regla 2 -------------------------------------
echo; echo "${BOLD}---- Regla 2: health no abierto por host externo ----${RESET}"

http_case "2.2" "Host externo, health, sin token -> 403" 403 "RBAC" \
  "$URL_EXT$HEALTH_PATH"

http_case "2.4" "Host externo, health, token valido -> 200" 200 "UP" \
  -H "Authorization: Bearer $TOKEN" "$URL_EXT$HEALTH_PATH"

# -------------------------------- Resumen ------------------------------------
echo
echo "${BOLD}================== RESUMEN ==================${RESET}"
for r in "${RESULTS[@]}"; do
  IFS='|' read -r st id desc detail <<< "$r"
  case "$st" in
    PASS) color="$GREEN" ;; *) color="$RED" ;;
  esac
  printf '%s%-4s%s %-5s %s\n' "$color" "$st" "$RESET" "$id" "$desc"
done
echo "---------------------------------------------"
echo "PASS: $PASSED   FAIL: $FAILED"
echo "Host interno y regla 1: ejecutar dentro del pod (README.md, seccion 6)."

(( FAILED == 0 ))
