"""Verificación de entrega en el fake channel de la plataforma (WhatsApp y Teams).

Replica lo que hace la prueba E2E de `Platform_test`:
    - `utils/aws/service/Cognito.java`: token `client_credentials` en
      `<COGNITO_TOKEN_URL>/oauth2/token`.
    - `tasks/VerifyChannelDelivery.java`:
      `GET <FAKE_CHANNEL_BASE_URL>/{whatsapp|teams}/get-messages/{user}` con
      `Authorization: Bearer <token>`, reintentando 5 veces cada 10 s.

Formato de los mensajes:
    - WhatsApp: `{"to": "<teléfono>", "text": {"body": "..."}, "type": "text", ...}`.
    - Teams: `{"channelId": "msteams", "recipient": {"id": "<uuid>"}, "text": "...",
      "type": "message"}`.
    - `404 {"error": "No messages found for user <id>"}`: todavía no llegó nada para ese usuario.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from pydantic import SecretStr

from campaigns_cli.errors import ExternalServiceError, ServiceAuthError, UsageError

if TYPE_CHECKING:
    import httpx

    from campaigns_cli.http import HttpClients
    from campaigns_cli.settings import Settings

TOKEN_PATH = "/oauth2/token"
NO_MESSAGES_MARKER = "No messages found"
# Margen para no usar un token a punto de vencer.
TOKEN_EXPIRY_MARGIN_SECONDS = 30
DEFAULT_TOKEN_TTL_SECONDS = 3600

REQUIRED_SETTINGS = (
    "cognito_token_url",
    "cognito_client_id",
    "cognito_client_secret",
    "fake_channel_base_url",
)


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    TEAMS = "teams"

    @property
    def expected_type(self) -> str:
        return "message" if self is Channel.TEAMS else "text"


_CHANNEL_ALIASES = {"whatsapp": Channel.WHATSAPP, "teams": Channel.TEAMS, "msteams": Channel.TEAMS}


def parse_channel(value: str) -> Channel:
    """`whatsapp`, `teams` o `msteams` (columna `canal` del CSV), sin importar mayúsculas."""
    channel = _CHANNEL_ALIASES.get(value.strip().lower())
    if channel is None:
        raise UsageError(f"Canal inválido '{value}': usa whatsapp, teams o msteams.")
    return channel


@dataclass(frozen=True)
class ChannelMessage:
    canal: Channel
    destinatario: str
    texto: str
    tipo: str
    raw: Any = None

    def matches(self, user: str, text: str) -> bool:
        return (
            self.destinatario == user
            and self.texto == text
            and self.tipo == self.canal.expected_type
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "canal": self.canal.value,
            "destinatario": self.destinatario,
            "texto": self.texto,
            "tipo": self.tipo,
        }


def normalize_message(item: Any) -> ChannelMessage:
    """Convierte un mensaje del fake channel al formato común; el canal sale de `channelId`."""
    data: dict[str, Any] = item if isinstance(item, dict) else {}
    tipo = str(data.get("type") or "").strip()
    if str(data.get("channelId") or "").lower() == "msteams":
        recipient = data.get("recipient")
        to = recipient.get("id", "") if isinstance(recipient, dict) else ""
        return ChannelMessage(
            Channel.TEAMS, str(to).strip(), str(data.get("text") or "").strip(), tipo, item
        )
    text = data.get("text")
    body = text.get("body", "") if isinstance(text, dict) else ""
    return ChannelMessage(
        Channel.WHATSAPP, str(data.get("to") or "").strip(), str(body).strip(), tipo, item
    )


def token_endpoint(url: str) -> str:
    base = url.rstrip("/")
    return base if base.endswith(TOKEN_PATH) else base + TOKEN_PATH


class CognitoAuth:
    """Token OAuth2 `client_credentials`; se reutiliza mientras no venza."""

    def __init__(
        self,
        client: httpx.Client,
        token_url: str,
        client_id: str,
        client_secret: SecretStr,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.url = token_endpoint(token_url)
        self.client_id = client_id
        self.client_secret = client_secret
        self.clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token and self.clock() < self._expires_at:
            return self._token
        response = self.client.post(
            self.url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret.get_secret_value(),
            },
        )
        # Nunca se incluye el cuerpo de la petición en los mensajes: lleva el secreto.
        if response.status_code in (400, 401, 403):
            raise ServiceAuthError(
                f"Cognito rechazó las credenciales (HTTP {response.status_code}). "
                "Revisa COGNITO_CLIENT_ID y COGNITO_CLIENT_SECRET en el .env."
            )
        if response.status_code != 200:
            raise ExternalServiceError(
                f"Cognito respondió HTTP {response.status_code} al pedir el token ({self.url})."
            )
        payload = _json(response)
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise ExternalServiceError("La respuesta de Cognito no trae access_token.")
        ttl = payload.get("expires_in", DEFAULT_TOKEN_TTL_SECONDS)
        ttl = ttl if isinstance(ttl, int | float) else DEFAULT_TOKEN_TTL_SECONDS
        self._token = str(token)
        self._expires_at = self.clock() + max(ttl - TOKEN_EXPIRY_MARGIN_SECONDS, 0)
        return self._token


@dataclass
class DeliveryResult:
    canal: Channel
    usuario: str
    texto: str
    entregado: bool
    intentos: int
    detalle: str
    mensaje: ChannelMessage | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "canal": self.canal.value,
            "usuario": self.usuario,
            "texto_esperado": self.texto,
            "entregado": self.entregado,
            "intentos": self.intentos,
            "detalle": self.detalle,
        }


class FakeChannel:
    def __init__(
        self,
        client: httpx.Client,
        base_url: str,
        auth: CognitoAuth,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.sleep = sleep

    def url(self, channel: Channel, user: str) -> str:
        return f"{self.base_url}/{channel.value}/get-messages/{quote(user, safe='')}"

    def messages(self, channel: Channel, user: str) -> list[ChannelMessage]:
        """Mensajes recibidos por el usuario; lista vacía si todavía no llegó ninguno."""
        url = self.url(channel, user)
        response = self.client.get(
            url,
            headers={
                "Authorization": f"Bearer {self.auth.token()}",
                "Content-Type": "application/json",
            },
        )
        status = response.status_code
        if status == 404:
            if NO_MESSAGES_MARKER in response.text:
                return []
            raise ExternalServiceError(
                f"El fake channel respondió 404 en {url}. Revisa FAKE_CHANNEL_BASE_URL."
            )
        if status in (401, 403):
            raise ServiceAuthError(f"El fake channel rechazó el token de Cognito (HTTP {status}).")
        if status != 200:
            raise ExternalServiceError(f"El fake channel respondió HTTP {status} en {url}.")
        payload = _json(response)
        if not isinstance(payload, list):
            raise ExternalServiceError(f"El fake channel no devolvió una lista en {url}.")
        return [normalize_message(item) for item in payload]

    def wait_for(
        self, channel: Channel, user: str, text: str, *, attempts: int, interval: float
    ) -> DeliveryResult:
        """Reintenta hasta encontrar un mensaje para `user` con `text` y el tipo del canal."""
        detail = ""
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self.sleep(interval)
            found = self.messages(channel, user)
            match = next((message for message in found if message.matches(user, text)), None)
            if match is not None:
                return DeliveryResult(
                    channel, user, text, True, attempt, "Mensaje entregado.", match
                )
            detail = _mismatch_detail(found, channel)
        return DeliveryResult(channel, user, text, False, attempts, detail)


def _mismatch_detail(found: list[ChannelMessage], channel: Channel) -> str:
    if not found:
        return "Sin mensajes para el usuario."
    last = found[-1]
    return (
        f"{len(found)} mensaje(s), ninguno coincide. Último: destinatario={last.destinatario}, "
        f"texto={last.texto}, tipo={last.tipo} (esperado {channel.expected_type})."
    )


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError(
            f"Respuesta inválida (no es JSON) de {response.request.url}."
        ) from exc


def fake_channel_from(settings: Settings, http: HttpClients) -> FakeChannel:
    """Arma el cliente del fake channel; exige las variables COGNITO_* y FAKE_CHANNEL_BASE_URL."""
    settings.require(*REQUIRED_SETTINGS)
    assert settings.cognito_client_secret is not None
    auth = CognitoAuth(
        http.cognito,
        str(settings.cognito_token_url),
        str(settings.cognito_client_id),
        settings.cognito_client_secret,
    )
    return FakeChannel(http.fake_channel, str(settings.fake_channel_base_url), auth)
