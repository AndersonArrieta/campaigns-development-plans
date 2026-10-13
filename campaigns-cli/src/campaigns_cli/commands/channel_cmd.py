"""Comandos `channel`: mensajes recibidos en el fake channel (solo lectura)."""

from typing import Annotated

import typer

from campaigns_cli.errors import TestFailedError
from campaigns_cli.output import info, render, success
from campaigns_cli.services.channel_service import Channel, fake_channel_from, parse_channel
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import get_state

app = typer.Typer(
    help="Consulta el fake channel (WhatsApp y Teams) con un token de Cognito.",
    no_args_is_help=True,
)

CanalOption = Annotated[
    Channel,
    typer.Option(
        "--canal",
        parser=parse_channel,
        metavar="whatsapp|teams",
        help="Canal: whatsapp, teams o msteams.",
    ),
]
UserOption = Annotated[
    str,
    typer.Option("--user", help="Usuario: teléfono en WhatsApp, recipient.id (UUID) en Teams."),
]


@app.command()
def messages(
    ctx: typer.Context,
    canal: CanalOption,
    user: UserOption,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, help="Máximo de mensajes.")] = 50,
) -> None:
    """Lista los mensajes que el fake channel recibió para un usuario."""
    state = get_state(ctx)
    found = fake_channel_from(state.settings, state.http).messages(canal, user)
    rows = [message.as_dict() for message in found[:limit]]
    render(rows, state.output, title=f"Mensajes de {user} en {canal.value}")
    if len(found) > limit:
        info(f"Se muestran {limit} de {len(found)} mensajes; usa --limit para ver más.")


@app.command()
def verify(
    ctx: typer.Context,
    canal: CanalOption,
    user: UserOption,
    text: Annotated[str, typer.Option("--text", help="Texto que debe haber llegado.")],
    attempts: Annotated[int, typer.Option("--attempts", min=1, help="Intentos.")] = 5,
    interval: Annotated[
        float, typer.Option("--interval", min=0, help="Segundos entre intentos.")
    ] = 10,
) -> None:
    """Verifica que el usuario recibió el texto (reintenta como la prueba E2E de Platform_test)."""
    state = get_state(ctx)
    channel = fake_channel_from(state.settings, state.http)
    if state.output is not OutputFormat.JSON:
        info(f"Buscando el mensaje en {channel.url(canal, user)} ({attempts} intento(s)).")
    result = channel.wait_for(canal, user, text, attempts=attempts, interval=interval)
    render(result.as_dict(), state.output, title="Entrega en el fake channel")
    if not result.entregado:
        raise TestFailedError(f"El mensaje no llegó tras {attempts} intento(s). {result.detalle}")
    success(f"Mensaje entregado (intento {result.intentos}).")
