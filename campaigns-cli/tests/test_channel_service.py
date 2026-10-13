import httpx
import pytest
from pydantic import SecretStr

from campaigns_cli.errors import ExternalServiceError, ServiceAuthError, UsageError
from campaigns_cli.services.channel_service import (
    Channel,
    CognitoAuth,
    FakeChannel,
    normalize_message,
    parse_channel,
    token_endpoint,
)
from tests.channel_fixtures import (
    BASE_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    EXPECTED_TEXT,
    TEAMS_USER,
    TOKEN_URL,
    WHATSAPP_USER,
    FakeServer,
    no_messages,
    ok,
    teams_message,
    whatsapp_message,
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()


def _auth(server: FakeServer, clock: Clock | None = None) -> CognitoAuth:
    return CognitoAuth(
        server.client(),
        TOKEN_URL,
        CLIENT_ID,
        SecretStr(CLIENT_SECRET),
        clock=clock or Clock(),
    )


def _channel(server: FakeServer, sleeps: list[float] | None = None) -> FakeChannel:
    recorded = sleeps if sleeps is not None else []
    return FakeChannel(server.client(), BASE_URL, _auth(server), sleep=recorded.append)


# --- canal ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("whatsapp", Channel.WHATSAPP),
        ("WhatsApp", Channel.WHATSAPP),
        ("teams", Channel.TEAMS),
        ("msteams", Channel.TEAMS),
    ],
)
def test_parse_channel(value: str, expected: Channel) -> None:
    assert parse_channel(value) is expected


def test_parse_channel_invalid() -> None:
    with pytest.raises(UsageError, match="Canal inválido"):
        parse_channel("telegram")


# --- token ---


@pytest.mark.parametrize(
    "url",
    [TOKEN_URL, f"{TOKEN_URL}/", f"{TOKEN_URL}/oauth2/token", f"{TOKEN_URL}/oauth2/token/"],
)
def test_token_endpoint_appends_path_once(url: str) -> None:
    assert token_endpoint(url) == f"{TOKEN_URL}/oauth2/token"


def test_token_request_uses_client_credentials(server: FakeServer) -> None:
    token = _auth(server).token()

    request = server.token_requests[0]
    assert token == "tok-1"
    assert str(request.url) == f"{TOKEN_URL}/oauth2/token"
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert server.form(request) == {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }


def test_token_is_reused_until_it_expires(server: FakeServer) -> None:
    clock = Clock()
    auth = _auth(server, clock)

    auth.token()
    clock.now = 3000
    auth.token()
    assert len(server.token_requests) == 1

    clock.now = 3571  # 3600 - 30 s de margen
    auth.token()
    assert len(server.token_requests) == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_rejected_credentials(server: FakeServer, status: int) -> None:
    server.token_status = status

    with pytest.raises(ServiceAuthError) as error:
        _auth(server).token()

    assert f"HTTP {status}" in str(error.value)
    assert CLIENT_SECRET not in str(error.value)


def test_token_server_error(server: FakeServer) -> None:
    server.token_status = 500

    with pytest.raises(ExternalServiceError, match="HTTP 500"):
        _auth(server).token()


def test_token_without_access_token(server: FakeServer) -> None:
    server.token_payload = {"token_type": "Bearer"}

    with pytest.raises(ExternalServiceError, match="access_token"):
        _auth(server).token()


# --- mensajes ---


def test_normalize_whatsapp_message() -> None:
    message = normalize_message(whatsapp_message())

    assert message.canal is Channel.WHATSAPP
    assert message.as_dict() == {
        "canal": "whatsapp",
        "destinatario": WHATSAPP_USER,
        "texto": EXPECTED_TEXT,
        "tipo": "text",
    }
    assert message.matches(WHATSAPP_USER, EXPECTED_TEXT)


def test_normalize_teams_message() -> None:
    message = normalize_message(teams_message())

    assert message.canal is Channel.TEAMS
    assert message.destinatario == TEAMS_USER
    assert message.texto == EXPECTED_TEXT
    assert message.matches(TEAMS_USER, EXPECTED_TEXT)


def test_normalize_tolerates_unexpected_shapes() -> None:
    message = normalize_message({"text": "plano", "type": "text"})

    assert message.texto == ""
    assert not message.matches("", "plano")


def test_messages_sends_bearer_token(server: FakeServer) -> None:
    server.inbox = [ok([whatsapp_message()])]

    found = _channel(server).messages(Channel.WHATSAPP, WHATSAPP_USER)

    request = server.message_requests[0]
    assert str(request.url) == f"{BASE_URL}/whatsapp/get-messages/{WHATSAPP_USER}"
    assert request.headers["authorization"] == "Bearer tok-1"
    assert [m.texto for m in found] == [EXPECTED_TEXT]


def test_messages_teams_path(server: FakeServer) -> None:
    server.inbox = [ok([teams_message()])]

    _channel(server).messages(Channel.TEAMS, TEAMS_USER)

    assert server.message_requests[0].url.path.endswith(f"/teams/get-messages/{TEAMS_USER}")


def test_user_is_url_encoded(server: FakeServer) -> None:
    channel = _channel(server)

    assert channel.url(Channel.TEAMS, "a b/c").endswith("/teams/get-messages/a%20b%2Fc")


def test_no_messages_is_empty_list(server: FakeServer) -> None:
    assert _channel(server).messages(Channel.WHATSAPP, WHATSAPP_USER) == []


def test_other_404_points_to_base_url(server: FakeServer) -> None:
    server.inbox = [httpx.Response(404, text="Not Found")]

    with pytest.raises(ExternalServiceError, match="FAKE_CHANNEL_BASE_URL"):
        _channel(server).messages(Channel.WHATSAPP, WHATSAPP_USER)


def test_rejected_token(server: FakeServer) -> None:
    server.inbox = [httpx.Response(401, json={"message": "Unauthorized"})]

    with pytest.raises(ServiceAuthError, match="HTTP 401"):
        _channel(server).messages(Channel.WHATSAPP, WHATSAPP_USER)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(500, text="boom"), "HTTP 500"),
        (httpx.Response(200, json={"items": []}), "no devolvió una lista"),
        (httpx.Response(200, text="<html>"), "no es JSON"),
    ],
)
def test_unexpected_responses(server: FakeServer, response: httpx.Response, message: str) -> None:
    server.inbox = [response]

    with pytest.raises(ExternalServiceError, match=message):
        _channel(server).messages(Channel.WHATSAPP, WHATSAPP_USER)


# --- espera de entrega ---


def test_wait_for_retries_until_delivered(server: FakeServer) -> None:
    server.inbox = [no_messages, no_messages, ok([whatsapp_message()])]
    sleeps: list[float] = []

    result = _channel(server, sleeps).wait_for(
        Channel.WHATSAPP, WHATSAPP_USER, EXPECTED_TEXT, attempts=5, interval=10
    )

    assert result.entregado is True
    assert result.intentos == 3
    assert sleeps == [10, 10]
    assert len(server.token_requests) == 1


def test_wait_for_checks_every_message(server: FakeServer) -> None:
    server.inbox = [ok([whatsapp_message(body="otro"), whatsapp_message()])]

    result = _channel(server).wait_for(
        Channel.WHATSAPP, WHATSAPP_USER, EXPECTED_TEXT, attempts=1, interval=0
    )

    assert result.entregado is True


def test_wait_for_gives_up_without_messages(server: FakeServer) -> None:
    sleeps: list[float] = []

    result = _channel(server, sleeps).wait_for(
        Channel.WHATSAPP, WHATSAPP_USER, EXPECTED_TEXT, attempts=3, interval=2
    )

    assert result.entregado is False
    assert result.intentos == 3
    assert result.detalle == "Sin mensajes para el usuario."
    assert sleeps == [2, 2]
    assert len(server.message_requests) == 3


def test_wait_for_reports_mismatch(server: FakeServer) -> None:
    wrong_type = {**whatsapp_message(), "type": "template"}
    server.inbox = [ok([wrong_type])]

    result = _channel(server).wait_for(
        Channel.WHATSAPP, WHATSAPP_USER, EXPECTED_TEXT, attempts=1, interval=0
    )

    assert result.entregado is False
    assert "tipo=template (esperado text)" in result.detalle
    assert result.as_dict()["texto_esperado"] == EXPECTED_TEXT
