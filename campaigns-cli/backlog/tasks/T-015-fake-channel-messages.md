---
id: T-015
aliases: [T-015]
title: "Grupo channel: token de Cognito y mensajes del fake channel"
status: todo
priority: P1
epic: E-entrega
estimate: L
depends_on: [T-003]
type: task
affects: [T-003]
created: 2026-10-13
---

# T-015 — Grupo `channel`: token de Cognito y mensajes del fake channel

## Objetivo
Consultar desde la CLI los mensajes que el **fake channel** recibió para un usuario, igual que el
paso "I verify the campaign was delivered successfully" de la prueba E2E de `Platform_test`, para
comprobar que una campaña llegó de punta a punta. Es la base de la etapa de entrega de
`trace run` ([[T-016-trace-entrega-canal|T-016]]).

Cómo lo hace hoy `Platform_test` (repo `NU0284001_Artemis_Chatbots_Platform_MR_Test`):
- `utils/aws/service/Cognito.java`: `POST <cognitoEndpoint>/oauth2/token` (agrega `/oauth2/token`
  si falta) con `application/x-www-form-urlencoded` y
  `grant_type=client_credentials&client_id=…&client_secret=…`; toma `access_token`. Status ≠ 200 → error.
- `tasks/VerifyChannelDelivery.java`: `GET <endpointGetMessageFake>/whatsapp/get-messages/{user}` o
  `/teams/get-messages/{user}` (Teams si el canal es `msteams`), con `Authorization: Bearer <token>`.
  Hasta 5 intentos con 10 s entre cada uno. Valida el **primer** mensaje de la lista:

| Canal | Destinatario | Texto | Tipo esperado |
|---|---|---|---|
| WhatsApp | `to` | `text.body` | `text` |
| Teams (`channelId = "msteams"`) | `recipient.id` (UUID) | `text` | `message` |

- `404 {"error":"No messages found for user <id>"}` = todavía no llegó nada (se reintenta).
- El test acepta cualquier certificado SSL (`configureUnirestSsl`).
- Propiedades de origen: `-DcognitoEndpoint`, `-DclientId`, `-DclientSecret`, `-DendpointGetMessageFake`.
- En dev: Cognito `https://chatbots-artemis-dev.auth.us-east-1.amazoncognito.com` y fake channel
  `https://informacion-ext-dev.apps.ambientesbc.com/artemis/platform/fake-channel/v1`.
- Solo existen los endpoints `GET …/get-messages/{user}`; no hay uno para enviar ni para borrar mensajes.

## Archivos a crear/modificar
- `pyproject.toml`, `uv.lock` — dependencia HTTP (propuesta: `httpx`)
- `src/campaigns_cli/settings.py` — `COGNITO_TOKEN_URL`, `COGNITO_CLIENT_ID`, `COGNITO_CLIENT_SECRET` (`SecretStr`), `FAKE_CHANNEL_BASE_URL`, `FAKE_CHANNEL_VERIFY_SSL` (por defecto `true`)
- `src/campaigns_cli/http.py` — fábrica del cliente HTTP (timeout, verificación SSL), equivalente a `aws.py`
- `src/campaigns_cli/services/channel_service.py` — `CognitoAuth.token()`, `FakeChannel.messages(canal, user)`, `FakeChannel.wait_for(canal, user, expected_text, attempts, interval)` y `ChannelMessage` normalizado (`canal`, `destinatario`, `texto`, `tipo`, `raw`)
- `src/campaigns_cli/commands/channel_cmd.py` — subgrupo `channel`
- `src/campaigns_cli/main.py` — registrar `channel`
- `src/campaigns_cli/errors.py` — traducir errores HTTP (conexión, 401/403, 5xx) a exit code 3
- `src/campaigns_cli/services/config_service.py`, `commands/config_cmd.py` — filas "Cognito" y "Fake channel" en `config check`
- `.env.example`
- `tests/test_channel_service.py`, `tests/test_channel_cmd.py`, `tests/test_settings.py`, `tests/test_config_check.py`
- `docs/configuracion.md`, `docs/comandos.md`, `docs/arquitectura.md`, `docs/README.md`
- `docs/adr/0008-cliente-http.md`

## Tareas
- [ ] Escribir ADR en `docs/adr/` (0008): cliente HTTP (`httpx` con `MockTransport` en pruebas vs. `urllib` de la librería estándar) y política de SSL (verificar por defecto; desactivable por ambiente con `FAKE_CHANNEL_VERIFY_SSL=false`, avisando por stderr).
- [ ] Variables nuevas en `Settings` y `.env.example` (sin valores de `CLIENT_ID`/`CLIENT_SECRET`; comentario con el origen en el pipeline de `Platform_test`). El secreto nunca se imprime ni aparece en errores.
- [ ] `CognitoAuth`: obtiene el token `client_credentials`, lo reutiliza dentro de la misma ejecución hasta `expires_in`; status ≠ 200 → error con el status y sin el cuerpo de la petición.
- [ ] `FakeChannel.messages`: GET con Bearer; `200` + lista → mensajes normalizados; `404` "No messages found" → lista vacía; otro status → error.
- [ ] `FakeChannel.wait_for`: reintenta hasta encontrar un mensaje cuyo destinatario, texto y tipo coincidan (busca en **todos** los mensajes de la lista, no solo el primero); `sleep` inyectable para pruebas.
- [ ] Comandos:
  - `campaigns channel messages --canal whatsapp|teams --user ID [-n 50]`: lista los mensajes (tabla o JSON).
  - `campaigns channel verify --canal whatsapp|teams --user ID --text TEXTO [--attempts 5] [--interval 10]`: exit 0 si llegó; exit 1 (`TestFailedError`) con el último motivo si no.
  - `--canal` acepta también `msteams` como alias de `teams`.
- [ ] `config check`: fila "Cognito" (`OK` si obtiene token, `FALTA CONFIG`, `SIN PERMISO` en 400/401) y "Fake channel" (`OK` si responde 200 o 404 con un usuario cualquiera).
- [ ] Exit code 3 pasa a significar "AWS o servicio externo": actualizar `errors.py` y `docs/arquitectura.md`.
- [ ] Documentar el grupo en `docs/comandos.md`, las variables en `docs/configuracion.md` y el estado en `docs/README.md`.

## Criterios de aceptación
- [ ] Token: la petición lleva `grant_type=client_credentials`, `client_id` y `client_secret` en form-urlencoded; `/oauth2/token` se agrega si falta.
- [ ] WhatsApp: una respuesta como `[{"messaging_product":"whatsapp","text":{"body":"Campaig_e2e_test_delivered_successfully"},"to":"574141179337","type":"text"}]` se normaliza y `verify --text Campaig_e2e_test_delivered_successfully` sale con 0.
- [ ] Teams: `recipient.id`, `text` y `type: "message"` se normalizan igual.
- [ ] `404 No messages found` en todos los intentos → `verify` sale con 1 tras `--attempts` intentos; `messages` muestra "Sin resultados" y sale con 0.
- [ ] Token rechazado (401) o fake channel caído → exit 3 con mensaje corto; con `--verbose`, traceback.
- [ ] `COGNITO_CLIENT_SECRET` no aparece en `config show` (enmascarado), en `repr` ni en mensajes de error.
- [ ] Ninguna prueba hace llamadas HTTP reales.

## Verificación
```bash
uv run pytest tests/test_channel_service.py tests/test_channel_cmd.py tests/test_settings.py tests/test_config_check.py -q
uv run pytest --cov=campaigns_cli
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run campaigns channel --help
test -f docs/adr/0008-cliente-http.md
# en dev (solo lectura; requiere COGNITO_* y FAKE_CHANNEL_* en el .env)
uv run campaigns channel messages --canal whatsapp --user 574141179337
uv run campaigns channel verify --canal whatsapp --user 574141179337 --text Campaig_e2e_test_delivered_successfully --attempts 1
```

## Notas
- `affects: [T-003]` porque amplía `config check` y la traducción de errores de esa tarjeta.
- Si el fake channel no conserva mensajes viejos, el `verify` de la verificación en dev puede salir con 1 sin ser un fallo de la CLI; en ese caso basta con que `messages` responda 200 o 404.
- Los valores de `clientId` y `clientSecret` están en las propiedades del pipeline de `Platform_test`; los pone el usuario en su `.env`.
