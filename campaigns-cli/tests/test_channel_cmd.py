import json

import httpx
import pytest
from typer.testing import CliRunner

from campaigns_cli.http import HttpClients
from campaigns_cli.main import app
from campaigns_cli.state import AppState
from tests.channel_fixtures import (
    CHANNEL_ENV,
    CLIENT_SECRET,
    EXPECTED_TEXT,
    TEAMS_USER,
    WHATSAPP_USER,
    FakeServer,
    no_messages,
    ok,
    teams_message,
    whatsapp_message,
)

runner = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def server(write_env, monkeypatch: pytest.MonkeyPatch) -> FakeServer:  # type: ignore[no-untyped-def]
    """`.env` con el fake channel configurado y los clientes HTTP apuntando al servidor falso."""
    write_env(CHANNEL_ENV)
    fake = FakeServer()

    def http(self: AppState) -> HttpClients:
        if self._http is None:
            self._http = HttpClients(self.settings, transport=fake.transport())
        return self._http

    monkeypatch.setattr(AppState, "http", property(http))
    return fake


def _verify(*extra: str) -> list[str]:
    return [
        "channel",
        "verify",
        "--canal",
        "whatsapp",
        "--user",
        WHATSAPP_USER,
        "--text",
        EXPECTED_TEXT,
        "--interval",
        "0",
        *extra,
    ]


def test_messages_table(server: FakeServer) -> None:
    server.inbox = [ok([whatsapp_message()])]

    result = runner.invoke(
        app, ["channel", "messages", "--canal", "whatsapp", "--user", WHATSAPP_USER]
    )

    assert result.exit_code == 0, result.output
    assert EXPECTED_TEXT in result.stdout
    assert WHATSAPP_USER in result.stdout


def test_messages_json_teams_alias(server: FakeServer) -> None:
    server.inbox = [ok([teams_message()])]

    result = runner.invoke(
        app,
        ["--output", "json", "channel", "messages", "--canal", "msteams", "--user", TEAMS_USER],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [
        {"canal": "teams", "destinatario": TEAMS_USER, "texto": EXPECTED_TEXT, "tipo": "message"}
    ]
    assert server.message_requests[0].url.path.endswith(f"/teams/get-messages/{TEAMS_USER}")


def test_messages_limit(server: FakeServer) -> None:
    server.inbox = [ok([whatsapp_message(body=f"m{i}") for i in range(3)])]

    result = runner.invoke(
        app,
        [
            "--output",
            "json",
            "channel",
            "messages",
            "--canal",
            "whatsapp",
            "--user",
            WHATSAPP_USER,
            "-n",
            "2",
        ],
    )

    assert len(json.loads(result.stdout)) == 2
    assert "Se muestran 2 de 3" in result.stderr


def test_messages_without_messages(server: FakeServer) -> None:
    result = runner.invoke(
        app, ["channel", "messages", "--canal", "whatsapp", "--user", WHATSAPP_USER]
    )

    assert result.exit_code == 0
    assert "Sin resultados" in result.stderr


def test_verify_delivered(server: FakeServer) -> None:
    server.inbox = [no_messages, ok([whatsapp_message()])]

    result = runner.invoke(app, ["--output", "json", *_verify()])

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["entregado"] is True
    assert report["intentos"] == 2


def test_verify_not_delivered(server: FakeServer) -> None:
    result = runner.invoke(app, _verify("--attempts", "2"))

    assert result.exit_code == 1
    assert "no llegó tras 2 intento(s)" in result.stderr
    assert len(server.message_requests) == 2


def test_invalid_channel(server: FakeServer) -> None:
    result = runner.invoke(
        app, ["channel", "messages", "--canal", "telegram", "--user", WHATSAPP_USER]
    )

    assert result.exit_code == 2
    assert server.requests == []


def test_missing_config(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(CHANNEL_ENV.replace(f"COGNITO_CLIENT_SECRET={CLIENT_SECRET}", ""))

    result = runner.invoke(app, ["channel", "messages", "--canal", "whatsapp", "--user", "1"])

    assert result.exit_code == 2
    assert "COGNITO_CLIENT_SECRET" in result.stderr


def test_rejected_credentials_exit_3_without_secret(server: FakeServer) -> None:
    server.token_status = 401

    result = runner.invoke(app, _verify())

    assert result.exit_code == 3
    assert "Cognito rechazó las credenciales" in result.stderr
    assert CLIENT_SECRET not in result.output


def test_connection_error_exit_3(server: FakeServer) -> None:
    server.error = httpx.ConnectError("conexión rechazada")

    result = runner.invoke(app, _verify())

    assert result.exit_code == 3
    assert "No se pudo conectar con https://cognito.test/oauth2/token" in result.stderr


def test_timeout_exit_3(server: FakeServer) -> None:
    server.error = httpx.ReadTimeout("lento")

    result = runner.invoke(app, _verify())

    assert result.exit_code == 3
    assert "no respondió a tiempo" in result.stderr


def test_ssl_verification_can_be_disabled(server: FakeServer, write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(CHANNEL_ENV + "FAKE_CHANNEL_VERIFY_SSL=false\n")
    server.inbox = [ok([whatsapp_message()])]

    result = runner.invoke(
        app, ["channel", "messages", "--canal", "whatsapp", "--user", WHATSAPP_USER]
    )

    assert result.exit_code == 0
    assert "no se verifica el certificado" in result.stderr


def test_config_show_masks_client_secret(server: FakeServer) -> None:
    result = runner.invoke(app, ["--output", "json", "config", "show"])

    rows = {row["variable"]: row["valor"] for row in json.loads(result.stdout)}
    assert CLIENT_SECRET not in result.stdout
    assert rows["COGNITO_CLIENT_SECRET"].startswith("su****")
    assert rows["FAKE_CHANNEL_VERIFY_SSL"] == "True"
