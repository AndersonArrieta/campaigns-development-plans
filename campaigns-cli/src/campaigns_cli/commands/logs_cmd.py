"""Comandos `logs`: CloudWatch Logs de las lambdas y demás componentes (solo lectura)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

import typer
from rich.markup import escape

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.output import console, info, render, to_json, warn
from campaigns_cli.services.logs_service import LogHit, LogsService
from campaigns_cli.settings import OutputFormat, Settings
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import colombia_now, parse_datetime, parse_since

app = typer.Typer(
    help="Consulta CloudWatch Logs de las lambdas de campañas (solo lectura, hora Colombia).",
    no_args_is_help=True,
)

TABLE_MESSAGE_CHARS = 300


class LambdaName(StrEnum):
    INGESTER = "ingester"
    SCHEDULER = "scheduler"


SinceOption = Annotated[
    str | None, typer.Option("--since", help="Ventana hacia atrás: 30m, 2h, 1d.")
]
FromOption = Annotated[
    str | None, typer.Option("--from", help="Desde 'YYYY-MM-DD HH:MM' (hora Colombia).")
]
ToOption = Annotated[
    str | None, typer.Option("--to", help="Hasta 'YYYY-MM-DD HH:MM' (hora Colombia).")
]
GroupOption = Annotated[
    list[str] | None, typer.Option("--group", "-g", help="Log group (se puede repetir).")
]


def _service(state: AppState) -> LogsService:
    return LogsService(state.aws.logs)


def _window(
    since: str | None, start: str | None, end: str | None, default_since: str
) -> tuple[datetime, datetime]:
    if since and (start or end):
        raise UsageError("Usa --since o --from/--to, no ambos.")
    now = colombia_now()
    if start:
        window_start = parse_datetime(start)
        window_end = parse_datetime(end) if end else now
    elif end:
        raise UsageError("--to requiere --from.")
    else:
        window_start, window_end = now - parse_since(since or default_since), now
    if window_start >= window_end:
        raise UsageError("El inicio del rango debe ser anterior al final.")
    return window_start, window_end


def _lambda_group(settings: Settings, name: LambdaName) -> str:
    group = settings.lambda_log_groups.get(name.value)
    if group is None:
        settings.require(f"{name.value}_lambda_name")
    return str(settings.lambda_log_groups[name.value])


def _resolve_groups(
    settings: Settings, groups: list[str] | None, lambdas: list[LambdaName] | None
) -> list[str]:
    """--group > --lambda > CAMPAIGNS_LOG_GROUPS > log groups de las lambdas configuradas."""
    if groups:
        return groups
    if lambdas:
        return [_lambda_group(settings, name) for name in lambdas]
    resolved = settings.effective_log_groups
    if not resolved:
        settings.require("campaigns_log_groups")
    return resolved


def _one_line(message: str) -> str:
    text = " ".join(message.split())
    if len(text) > TABLE_MESSAGE_CHARS:
        return text[: TABLE_MESSAGE_CHARS - 1] + "…"
    return text


def _hit_row(hit: LogHit) -> dict[str, str]:
    return {
        "hora": hit.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "componente": hit.component,
        "mensaje": _one_line(hit.message),
    }


@app.command()
def groups(
    ctx: typer.Context,
    prefix: Annotated[
        str, typer.Option("--prefix", help="Prefijo del log group.")
    ] = "/aws/lambda/nu0284001-artemis",
) -> None:
    """Lista los log groups que empiezan por un prefijo (para descubrir nombres)."""
    state = get_state(ctx)
    found = _service(state).list_groups(prefix)
    render(found, state.output, title=f"Log groups con prefijo {prefix}")


@app.command()
def search(
    ctx: typer.Context,
    term: Annotated[
        str, typer.Option("--id", help="Texto a buscar: notification_id, campaign_id, etc.")
    ],
    since: SinceOption = None,
    start: FromOption = None,
    end: ToOption = None,
    group: GroupOption = None,
    lambda_: Annotated[
        list[LambdaName] | None,
        typer.Option("--lambda", "-l", help="Solo esa lambda (se puede repetir)."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=10000)] = 200,
) -> None:
    """Busca un texto en los logs con Logs Insights y muestra en qué componente aparece."""
    state = get_state(ctx)
    settings = state.settings
    log_groups = _resolve_groups(settings, group, lambda_)
    window_start, window_end = _window(since, start, end, default_since="24h")

    info(
        f"Buscando '{term}' en {len(log_groups)} log group(s) entre "
        f"{window_start:%Y-%m-%d %H:%M} y {window_end:%Y-%m-%d %H:%M} (hora Colombia)..."
    )
    result = _service(state).search(
        log_groups,
        term,
        window_start,
        window_end,
        limit=limit,
        timeout=settings.cli_wait_timeout_seconds,
        poll_interval=settings.cli_poll_interval_seconds,
    )

    if state.output is OutputFormat.JSON:
        render(
            {"hits": [hit.as_dict() for hit in result.hits], "resumen": result.summary()},
            state.output,
        )
    else:
        render(
            [_hit_row(hit) for hit in result.hits], state.output, title=f"Coincidencias de {term}"
        )
        summary = [
            {**row, "coincidencias": row["coincidencias"] or "✗ 0"} for row in result.summary()
        ]
        render(summary, state.output, title="Resumen por componente")

    if len(result.hits) >= limit:
        warn(f"Se alcanzó el límite de {limit} resultados; usa --limit o acota el rango.")
    if not result.hits:
        raise TestFailedError(f"'{term}' no aparece en los logs del rango consultado.")


@app.command()
def tail(
    ctx: typer.Context,
    lambda_: Annotated[
        LambdaName | None, typer.Option("--lambda", "-l", help="Lambda a consultar.")
    ] = None,
    group: Annotated[str | None, typer.Option("--group", "-g", help="Log group.")] = None,
    since: SinceOption = None,
    start: FromOption = None,
    end: ToOption = None,
    pattern: Annotated[
        str | None, typer.Option("--filter", help="Solo eventos que contengan este texto.")
    ] = None,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Sigue mostrando eventos nuevos (Ctrl+C).")
    ] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1)] = 100,
) -> None:
    """Muestra los eventos recientes de una lambda o log group."""
    if bool(lambda_) == bool(group):
        raise UsageError("Indica --lambda o --group (uno de los dos).")
    if follow and end:
        raise UsageError("--follow no admite --to.")
    state = get_state(ctx)
    log_group = _lambda_group(state.settings, lambda_) if lambda_ is not None else str(group)
    window_start, window_end = _window(since, start, end, default_since="15m")
    service = _service(state)

    if follow:
        _follow(state, service, log_group, window_start, pattern)
        return

    hits, truncated = service.events(
        log_group, window_start, window_end if end else None, pattern=pattern, limit=limit
    )
    if truncated:
        warn(f"Se muestran los últimos {limit} eventos; usa --limit o acota el rango.")
    if state.output is OutputFormat.JSON:
        render([hit.as_dict() for hit in hits], state.output)
        return
    if not hits:
        info("Sin eventos en el rango consultado.")
        return
    for hit in hits:
        console.print(_tail_line(hit), highlight=False)


def _follow(
    state: AppState,
    service: LogsService,
    log_group: str,
    start: datetime,
    pattern: str | None,
) -> None:
    interval = state.settings.cli_poll_interval_seconds
    info(f"Siguiendo {log_group} cada {interval}s (Ctrl+C para salir)...")
    try:
        for hit in service.follow(log_group, start, pattern=pattern, interval=interval):
            if state.output is OutputFormat.JSON:
                console.out(to_json(hit.as_dict()).replace("\n", " "), highlight=False)
            else:
                console.print(_tail_line(hit), highlight=False)
    except KeyboardInterrupt:
        info("Seguimiento detenido.")


def _tail_line(hit: LogHit) -> str:
    return f"[dim]{hit.timestamp:%Y-%m-%d %H:%M:%S}[/dim]  {escape(hit.message)}"
