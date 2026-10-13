"""Servidor falso de Cognito y del fake channel sobre `httpx.MockTransport` (sin red)."""

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx

TOKEN_URL = "https://cognito.test"
BASE_URL = "https://fake-channel.test/artemis/platform/fake-channel/v1"
CLIENT_ID = "client-id-test"
CLIENT_SECRET = "super-secreto-123"
WHATSAPP_USER = "574141179337"
TEAMS_USER = "27060555-ecc0-4aad-85b6-9a663cd04331"
EXPECTED_TEXT = "Campaig_e2e_test_delivered_successfully"

CHANNEL_ENV = f"""
COGNITO_TOKEN_URL={TOKEN_URL}
COGNITO_CLIENT_ID={CLIENT_ID}
COGNITO_CLIENT_SECRET={CLIENT_SECRET}
FAKE_CHANNEL_BASE_URL={BASE_URL}
"""


def whatsapp_message(to: str = WHATSAPP_USER, body: str = EXPECTED_TEXT) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "text": {"body": body},
        "to": to,
        "type": "text",
    }


def teams_message(to: str = TEAMS_USER, text: str = EXPECTED_TEXT) -> dict[str, Any]:
    return {"channelId": "msteams", "recipient": {"id": to}, "text": text, "type": "message"}


def no_messages(user: str) -> httpx.Response:
    return httpx.Response(404, json={"error": f"No messages found for user {user}"})


class FakeServer:
    """Responde el token y, por cada GET, la siguiente respuesta de `inbox` (repite la última)."""

    def __init__(self) -> None:
        self.token_status = 200
        self.token_payload: dict[str, Any] = {"access_token": "tok-1", "expires_in": 3600}
        self.inbox: list[httpx.Response | Callable[[str], httpx.Response]] = []
        self.requests: list[httpx.Request] = []
        self.error: Exception | None = None

    @property
    def token_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "POST"]

    @property
    def message_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "GET"]

    def form(self, request: httpx.Request) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if request.method == "POST":
            return httpx.Response(self.token_status, json=self.token_payload)
        user = request.url.path.rsplit("/", 1)[-1]
        if not self.inbox:
            return no_messages(user)
        index = min(len(self.message_requests), len(self.inbox)) - 1
        response = self.inbox[index]
        return response(user) if callable(response) else response

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport())


def ok(messages: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(messages))
