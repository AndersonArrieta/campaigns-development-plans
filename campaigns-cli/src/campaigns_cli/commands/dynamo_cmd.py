"""Comandos `dynamo`: consultas a las tablas de campañas y de logs y borrado de datos de prueba."""

from datetime import datetime
from typing import Annotated, Any

import typer
from rich.markup import escape

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.guards import confirm_destructive, ensure_not_prod
from campaigns_cli.output import console, info, render, to_json, warn
from campaigns_cli.services.clean_service import CleanPlan, TableChoice, execute, plan_clean
from campaigns_cli.services.dynamo_service import (
    CampaignsTable,
    LogEntry,
    LogsTable,
    QueryResult,
    follow_logs,
    parse_log_entry,
)
from campaigns_cli.services.history_service import (
    HistoryWindow,
    campaign_detail,
    classify_rows,
    load_history,
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
    help="Consulta las tablas DynamoDB de campañas y de logs y borra los datos de prueba.",
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
SinceOption = Annotated[
    str | None, typer.Option("--since", help="Ventana hacia atrás: 30m, 2h, 1d (def. 24h).")
]
FromOption = Annotated[str | None, typer.Option("--from", help="Desde 'YYYY-MM-DD HH:MM' (UTC).")]
ToOption = Annotated[str | None, typer.Option("--to", help="Hasta 'YYYY-MM-DD HH:MM' (UTC).")]
DetailsOption = Annotated[
    bool, typer.Option("--details", help="Incluye el detalle de errores de cada carga.")
]
TableOption = Annotated[
    TableChoice, typer.Option("--table", help="Tabla: campaigns, logs o all (las dos).")
]


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
    """Muestra un registro de la tabla de campañas; sin --datetime, todas sus reprogramaciones."""
    state = get_state(ctx)
    table = _campaigns(state)
    if scheduled:
        result = table.get(notification_id, to_dynamo(parse_datetime(scheduled)))
        if not result.items:
            raise TestFailedError(f"No existe el notification_id {notification_id}.")
        render(result.items[0], state.output, title=f"Notificación {notification_id}")
        return

    result = table.by_notification(notification_id)
    _report(result, None)
    if not result.items:
        raise TestFailedError(f"No existe el notification_id {notification_id}.")
    rows = [
        row.with_classification()
        for timeline in classify_rows(result.items, colombia_now())
        for row in timeline.rows
    ]
    if state.output is OutputFormat.JSON:
        render(rows, state.output)
        return
    if len(rows) == 1:
        render(rows[0], state.output, title=f"Notificación {notification_id}")
        return
    render(
        rows,
        state.output,
        title=f"Notificación {notification_id}: {len(rows)} filas (hora Colombia)",
        columns=(*CAMPAIGN_COLUMNS, "tipo", "estado"),
    )


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
        typer.Option("--date", help="Día YYYY-MM-DD (hora Colombia)."),
    ] = None,
    hour: Annotated[
        int | None,
        typer.Option("--hour", min=0, max=23, help="Solo esa hora del día (sin --date, hoy)."),
    ] = None,
    start: Annotated[
        str | None, typer.Option("--from", help="Desde 'YYYY-MM-DD HH:MM' (usar con --to).")
    ] = None,
    end: Annotated[str | None, typer.Option("--to", help="Hasta 'YYYY-MM-DD HH:MM'.")] = None,
    app_id: AppIdOption = None,
    user: UserOption = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-n",
            min=1,
            help="Máximo de registros (por defecto 500 con fecha; sin fecha, todos por tabla).",
        ),
    ] = None,
) -> None:
    """Sin fecha, todas las filas de las dos tablas (scan); con fecha, query por hora."""
    if (start or end) and (date or hour is not None):
        raise UsageError("Usa --date/--hour o --from/--to, no ambos.")
    if not (start or end or date or hour is not None):
        _dump_tables(get_state(ctx), TableChoice.ALL, app_id, limit, user=user)
        return
    limit = 500 if limit is None else limit
    if start or end:
        if not (start and end):
            raise UsageError("--from y --to van juntos.")
        range_start, range_end = parse_datetime(start), parse_datetime(end)
        if range_start > range_end:
            raise UsageError("--from debe ser anterior a --to.")
    else:
        day = parse_datetime(date) if date else colombia_now()  # --hour sin --date: hoy
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


@app.command()
def purge(
    ctx: typer.Context,
    campaign_id: Annotated[
        str, typer.Option("--campaign-id", help="campaign_id (uno por archivo CSV).")
    ],
) -> None:
    """Borra de la tabla de campañas los registros de un campaign_id con app_id CLI_TEST_APP_ID."""
    state = get_state(ctx)
    settings = state.settings
    ensure_not_prod(settings, "dynamo purge")
    table = _campaigns(state)
    plan = table.plan_purge(campaign_id, settings.cli_test_app_id)
    if plan.scanned:
        warn("Búsqueda con scan: recorre toda la tabla (más lento y costoso).")
    if plan.skipped:
        warn(
            f"Se omiten {len(plan.skipped)} registro(s) de otro app_id: "
            f"solo se borra {settings.cli_test_app_id} (CLI_TEST_APP_ID)."
        )
    if plan.to_delete:
        confirm_destructive(
            state,
            f"¿Borrar {len(plan.to_delete)} registro(s) de la campaña {campaign_id} "
            f"(app_id {settings.cli_test_app_id}) de la tabla {table.table_name} "
            f"en {settings.campaigns_env}?",
        )
    else:
        info("No hay registros que borrar.")
    result = table.purge(plan)
    render(result.as_dict(), state.output, title="Resultado de dynamo purge")
    if result.failed:
        raise TestFailedError(f"No se pudieron borrar {result.failed} registro(s).")


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
    since: SinceOption = None,
    start: FromOption = None,
    end: ToOption = None,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Sigue mostrando las cargas nuevas (Ctrl+C).")
    ] = False,
    details: DetailsOption = False,
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
        _render_error_details(state, entries)


def _render_error_details(state: AppState, entries: list[LogEntry]) -> None:
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


@app.command()
def history(
    ctx: typer.Context,
    app_id: AppIdOption = None,
    since: SinceOption = None,
    start: FromOption = None,
    end: ToOption = None,
    details: DetailsOption = False,
    limit: LimitOption = 50,
) -> None:
    """Una línea por carga del ingester con las filas que dejó y sus reprogramaciones."""
    if since and start:
        raise UsageError("Usa --since o --from/--to, no ambos.")
    state = get_state(ctx)
    logs_table, campaigns_table = _logs(state), _campaigns(state)
    window_start, window_end = _logs_window(since, start, end)
    result = load_history(
        logs_table,
        campaigns_table,
        HistoryWindow(window_start, window_end, app_id, limit),
        colombia_now(),
    )
    if result.scanned:
        warn("Consulta con scan: recorre toda la tabla (más lento y costoso).")
    if result.truncated:
        warn(f"Se muestran las primeras {limit} cargas; usa --limit para ver más.")

    if state.output is OutputFormat.JSON:
        render([load.as_dict() for load in result.loads], state.output)
        return
    render(
        [load.summary() for load in result.loads],
        state.output,
        title=f"Historial de cargas desde {to_dynamo(window_start)} UTC",
    )
    if result.loads:
        info("Fecha de la carga en UTC; filas, reprogramados y pendientes de la tabla de campañas.")
    if details:
        _render_error_details(state, [load.entry for load in result.loads])


@app.command()
def campaign(
    ctx: typer.Context,
    campaign_id: Annotated[
        str, typer.Option("--campaign-id", help="campaign_id (uno por archivo CSV).")
    ],
) -> None:
    """Detalle de un CSV: su carga en logs y la línea de tiempo de cada notification_id."""
    state = get_state(ctx)
    detail = campaign_detail(_logs(state), _campaigns(state), campaign_id, colombia_now())
    if detail.scanned:
        warn("Consulta con scan: recorre toda la tabla (más lento y costoso).")
    if not detail.found:
        raise TestFailedError(f"No hay cargas ni filas del campaign_id {campaign_id}.")

    if state.output is OutputFormat.JSON:
        render(detail.as_dict(), state.output)
        return
    render(
        [entry.summary() for entry in detail.loads],
        state.output,
        title=f"Cargas del campaign_id {campaign_id} (fecha UTC)",
    )
    for timeline in detail.timelines:
        if not timeline.rescheduled:
            continue
        render(
            [row.summary() for row in timeline.rows],
            state.output,
            title=f"Notificación {timeline.notification_id} · usuario {timeline.first.get('user')}",
        )
    render(detail.stats.as_dict(), state.output, title="Resumen (filas de la tabla de campañas)")


@app.command()
def dump(
    ctx: typer.Context,
    table: TableOption = TableChoice.ALL,
    app_id: AppIdOption = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-n", min=1, help="Máximo de filas por tabla.")
    ] = None,
) -> None:
    """Todas las filas de las tablas (para guardar evidencias con --output json)."""
    _dump_tables(get_state(ctx), table, app_id, limit)


def _dump_tables(
    state: AppState,
    table: TableChoice,
    app_id: str | None,
    limit: int | None,
    user: str | None = None,
) -> None:
    """Scan de las tablas elegidas; `user` solo filtra la de campañas (los logs no lo tienen)."""
    data: dict[str, list[dict[str, Any]]] = {}
    if table.includes_campaigns:
        result = _campaigns(state).all(app_id, limit=limit, user=user)
        _report(result, limit)
        data["campaigns"] = result.items
    if table.includes_logs:
        result = _logs(state).all(app_id, limit=limit)
        _report(result, limit)
        data["logs"] = result.items

    if state.output is OutputFormat.JSON:
        render(data, state.output)
        return
    if "campaigns" in data:
        render(
            data["campaigns"],
            state.output,
            title="Tabla de campañas (hora Colombia)",
            columns=CAMPAIGN_COLUMNS,
        )
    if "logs" in data:
        render(
            [parse_log_entry(item).summary() for item in data["logs"]],
            state.output,
            title="Tabla de logs (fecha UTC)",
        )


@app.command()
def clean(
    ctx: typer.Context,
    table: TableOption = TableChoice.ALL,
    campaign_id: Annotated[
        str | None,
        typer.Option("--campaign-id", help="Solo lo que dejó ese CSV (si no, vacía las tablas)."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Muestra qué se borraría, sin borrar.")
    ] = False,
) -> None:
    """Vacía las tablas de campañas y de logs, o borra solo lo de un campaign_id."""
    state = get_state(ctx)
    settings = state.settings
    ensure_not_prod(settings, "dynamo clean")
    campaigns_table = _campaigns(state) if table.includes_campaigns else None
    logs_table = _logs(state) if table.includes_logs else None

    plan = plan_clean(campaigns_table, logs_table, colombia_now(), campaign_id)
    _show_plan(state, plan)
    if dry_run:
        info("--dry-run: no se borró nada.")
        if state.output is OutputFormat.JSON:
            render({"plan": plan.as_dict(), "resultado": None}, state.output)
        return

    if plan.total:
        names = ", ".join(f"{item.table} ({item.table_name})" for item in plan.tables)
        scope = f"del campaign_id {campaign_id}" if campaign_id else "(vaciado completo)"
        confirm_destructive(
            state,
            f"¿Borrar {plan.total} fila(s) {scope} en {settings.campaigns_env}: {names}?",
        )
    result = execute(plan)
    if state.output is OutputFormat.JSON:
        render({"plan": plan.as_dict(), "resultado": result.as_dicts()}, state.output)
    else:
        render(result.as_dicts(), state.output, title="Resultado de dynamo clean")
    if not result.ok:
        failed = sum(item.failed for item in result.tables)
        remaining = sum(item.remaining for item in result.tables)
        raise TestFailedError(
            f"El borrado no quedó completo: {failed} fallida(s) y {remaining} restante(s) "
            "(pueden ser filas escritas durante el borrado)."
        )


def _show_plan(state: AppState, plan: CleanPlan) -> None:
    if plan.scanned:
        warn("Búsqueda con scan: recorre toda la tabla (más lento y costoso).")
    scope = f"del campaign_id {plan.campaign_id}" if plan.campaign_id else "de las tablas"
    for item in plan.tables:
        info(
            f"{item.table} ({item.table_name}): {len(item.rows)} fila(s) {scope}"
            + (
                f"; {item.rescheduled} reprogramada(s), {item.pending} pendiente(s), "
                f"{item.in_progress} en curso"
                if item.table == "campaigns"
                else ""
            )
            + "."
        )
    if plan.in_progress:
        warn(
            f"{plan.in_progress} fila(s) están EN_CURSO: el scheduler puede estar procesándolas "
            "en este momento."
        )
    if state.output is OutputFormat.TABLE:
        render([item.summary() for item in plan.tables], state.output, title="Plan de borrado")
        if plan.total:
            render(plan.by_app_rows(), state.output, title="Filas por app_id")
