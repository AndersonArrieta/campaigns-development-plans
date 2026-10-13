"""Comandos `dynamo`: consultas de solo lectura a las tablas de campañas y de logs."""

from datetime import datetime
from typing import Annotated, Any

import typer
from rich.markup import escape

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.output import console, info, render, to_json, warn
from campaigns_cli.services.dynamo_service import (
    CampaignsTable,
    LogEntry,
    LogsTable,
    QueryResult,
    follow_logs,
    parse_log_entry,
)
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import (
    colombia_now,
    hour_floor,
    parse_datetime,
    parse_since,
    to_dynamo,
    utc_now,
)

app = typer.Typer(
    help="Consulta las tablas DynamoDB de campañas y de logs (solo lectura).",
    no_args_is_help=True,
)

CAMPAIGN_COLUMNS = (
    "datetime",
    "notification_id",
    "campaign_id",
    "app_id",
    "channel",
    "user",
    "notification_node",
    "retries",
)

LimitOption = Annotated[int, typer.Option("--limit", "-n", min=1, help="Máximo de registros.")]
AppIdOption = Annotated[str | None, typer.Option("--app-id", help="Filtra por app_id.")]
UserOption = Annotated[str | None, typer.Option("--user", help="Filtra por usuario.")]


def _campaigns(state: AppState) -> CampaignsTable:
    settings = state.settings
    settings.require("campaigns_table_name")
    return CampaignsTable(
        state.aws.dynamodb,
        str(settings.campaigns_table_name),
        settings.campaigns_table_campaign_index,
    )


def _logs(state: AppState) -> LogsTable:
    settings = state.settings
    settings.require("campaigns_logs_table_name")
    return LogsTable(state.aws.dynamodb, str(settings.campaigns_logs_table_name))


def _report(result: QueryResult, limit: int | None) -> None:
    if result.scanned:
        warn("Consulta con scan: recorre toda la tabla (más lento y costoso).")
    if result.truncated:
        warn(f"Se muestran los primeros {limit} registros; usa --limit para ver más.")


def _render_campaigns(state: AppState, result: QueryResult, title: str) -> None:
    if state.output is OutputFormat.JSON:
        render(result.items, state.output)
        return
    render(result.items, state.output, title=title, columns=CAMPAIGN_COLUMNS)
    if result.items:
        info(f"{len(result.items)} registro(s). Las fechas están en hora Colombia.")


@app.command()
def get(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Option("--notification-id", help="notification_id.")],
    scheduled: Annotated[
        str | None,
        typer.Option(
            "--datetime",
            help="Fecha programada 'YYYY-MM-DD HH:00:00'. Sin ella se hace un scan.",
        ),
    ] = None,
) -> None:
    """Muestra un registro de la tabla de campañas con todos sus atributos."""
    state = get_state(ctx)
    key_datetime = to_dynamo(parse_datetime(scheduled)) if scheduled else None
    result = _campaigns(state).get(notification_id, key_datetime)
    _report(result, None)
    if not result.items:
        raise TestFailedError(f"No existe el notification_id {notification_id}.")
    render(result.items[0], state.output, title=f"Notificación {notification_id}")


@app.command()
def find(
    ctx: typer.Context,
    campaign_id: Annotated[
        str | None, typer.Option("--campaign-id", help="campaign_id (uno por archivo CSV).")
    ] = None,
    user: UserOption = None,
    app_id: AppIdOption = None,
    limit: LimitOption = 200,
) -> None:
    """Busca registros por campaign_id, usuario y/o app_id."""
    if not (campaign_id or user or app_id):
        raise UsageError("Indica al menos uno: --campaign-id, --user o --app-id.")
    state = get_state(ctx)
    result = _campaigns(state).find(campaign_id=campaign_id, user=user, app_id=app_id, limit=limit)
    _report(result, limit)
    _render_campaigns(state, result, title="Registros de campaña")


@app.command("list")
def list_(
    ctx: typer.Context,
    date: Annotated[
        str | None,
        typer.Option("--date", help="Día YYYY-MM-DD (por defecto hoy, hora Colombia)."),
    ] = None,
    hour: Annotated[
        int | None, typer.Option("--hour", min=0, max=23, help="Solo esa hora del día.")
    ] = None,
    start: Annotated[
        str | None, typer.Option("--from", help="Desde 'YYYY-MM-DD HH:MM' (usar con --to).")
    ] = None,
    end: Annotated[str | None, typer.Option("--to", help="Hasta 'YYYY-MM-DD HH:MM'.")] = None,
    app_id: AppIdOption = None,
    user: UserOption = None,
    limit: LimitOption = 500,
) -> None:
    """Lista los registros programados en un día, una hora o un rango (query por hora)."""
    if (start or end) and (date or hour is not None):
        raise UsageError("Usa --date/--hour o --from/--to, no ambos.")
    if start or end:
        if not (start and end):
            raise UsageError("--from y --to van juntos.")
        range_start, range_end = parse_datetime(start), parse_datetime(end)
        if range_start > range_end:
            raise UsageError("--from debe ser anterior a --to.")
    else:
        day = parse_datetime(date) if date else colombia_now()
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        if hour is None:
            range_start, range_end = day, day.replace(hour=23)
        else:
            range_start = range_end = day.replace(hour=hour)

    state = get_state(ctx)
    result = _campaigns(state).list_range(
        range_start, range_end, app_id=app_id, user=user, limit=limit
    )
    _report(result, limit)
    title = f"Programados {to_dynamo(hour_floor(range_start))} → {to_dynamo(hour_floor(range_end))}"
    _render_campaigns(state, result, title=title)


def _logs_window(
    since: str | None, start: str | None, end: str | None
) -> tuple[datetime, datetime | None]:
    if start:
        return parse_datetime(start), parse_datetime(end) if end else None
    if end:
        raise UsageError("--to requiere --from.")
    return utc_now() - parse_since(since or "24h"), None


@app.command()
def logs(
    ctx: typer.Context,
    app_id: AppIdOption = None,
    since: Annotated[
        str | None, typer.Option("--since", help="Ventana hacia atrás: 30m, 2h, 1d (def. 24h).")
    ] = None,
    start: Annotated[
        str | None, typer.Option("--from", help="Desde 'YYYY-MM-DD HH:MM' (UTC).")
    ] = None,
    end: Annotated[str | None, typer.Option("--to", help="Hasta 'YYYY-MM-DD HH:MM' (UTC).")] = None,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Sigue mostrando las cargas nuevas (Ctrl+C).")
    ] = False,
    details: Annotated[
        bool, typer.Option("--details", help="Incluye el detalle de errores de cada carga.")
    ] = False,
    limit: LimitOption = 50,
) -> None:
    """Muestra las cargas de campañas registradas por el ingester (tabla de logs)."""
    if since and start:
        raise UsageError("Usa --since o --from/--to, no ambos.")
    if follow and end:
        raise UsageError("--follow no admite --to.")
    state = get_state(ctx)
    table = _logs(state)
    window_start, window_end = _logs_window(since, start, end)

    if follow:
        _follow(state, table, app_id, window_start)
        return

    if app_id:
        result = table.by_app(app_id, window_start, window_end, limit=limit)
    else:
        result = table.recent(window_start, window_end, limit=limit)
    _report(result, limit)
    entries = [parse_log_entry(item) for item in result.items]

    if state.output is OutputFormat.JSON:
        render([entry.as_dict() for entry in entries], state.output)
        return
    render(
        [entry.summary() for entry in entries],
        state.output,
        title=f"Cargas de campañas desde {to_dynamo(window_start)} UTC",
    )
    if details:
        errors = [
            {"fecha": entry.datetime, "app_id": entry.app_id, "detalle": to_json(detail)}
            for entry in entries
            for detail in entry.error_details
        ]
        if errors:
            render(errors, state.output, title="Detalle de errores")


def _follow(state: AppState, table: LogsTable, app_id: str | None, start: datetime) -> None:
    interval = state.settings.cli_poll_interval_seconds

    def fetch(since: datetime) -> list[dict[str, Any]]:
        if app_id:
            return table.by_app(app_id, since).items
        return table.recent(since).items

    info(f"Siguiendo cargas desde {to_dynamo(start)} UTC cada {interval}s (Ctrl+C para salir)...")
    try:
        for entry in follow_logs(fetch, start, interval=interval):
            if state.output is OutputFormat.JSON:
                console.out(to_json(entry.as_dict()).replace("\n", " "), highlight=False)
                continue
            console.print(_follow_line(entry), highlight=False)
    except KeyboardInterrupt:
        info("Seguimiento detenido.")


def _follow_line(entry: LogEntry) -> str:
    color = {"SUCCESSFUL": "green", "PARTIALLY_SUCCESSFUL": "yellow"}.get(entry.status, "red")
    stats = (
        f"procesados={entry.total} exitosos={entry.successful} "
        f"omitidos={entry.omitted} errores={entry.errors}"
    )
    return (
        f"{escape(entry.datetime)}  {escape(entry.app_id)}  "
        f"[{color}]{escape(entry.status)}[/{color}]  {stats}  "
        f"campaign_id={escape(entry.campaign_id or '-')}  archivo={escape(entry.file or '-')}"
    )
