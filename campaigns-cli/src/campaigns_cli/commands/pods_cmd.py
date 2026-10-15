"""Comandos `pods`: logs de los pods de campaigns y engine en EKS (solo lectura)."""

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated

import typer
from rich.markup import escape

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.output import console, err_console, info, render, to_json, warn
from campaigns_cli.services.k8s_service import (
    Component,
    ComponentSummary,
    Pod,
    PodLogLine,
    PodsService,
    SelectedLine,
    StreamEnd,
    component_selectors,
    pods_service_from,
    select_lines,
    summarize,
)
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import parse_since

app = typer.Typer(
    help="Logs de los pods de campaigns y engine en EKS (solo lectura, hora Colombia).",
    no_args_is_help=True,
)

DEFAULT_TAIL = 1000
NOTIFICATION_SINCE = "24h"
MIN_TERM_LENGTH = 6


class ComponentChoice(StrEnum):
    CAMPAIGNS = "campaigns"
    ENGINE = "engine"
    ALL = "all"


SelectorOption = Annotated[
    str | None,
    typer.Option(
        "--selector", "-l", help="Selector de etiquetas (tiene prioridad sobre --component)."
    ),
]
ComponentOption = Annotated[
    list[ComponentChoice] | None,
    typer.Option(
        "--component",
        "-k",
        help="campaigns, engine o all (se puede repetir). Por defecto campaigns.",
    ),
]


@dataclass(frozen=True)
class Target:
    component: str | None
    selector: str


def _service(state: AppState) -> PodsService:
    return pods_service_from(state.settings, state.aws, state.http)


def _targets(
    state: AppState,
    selector: str | None,
    choices: list[ComponentChoice] | None,
    default: list[Component],
) -> list[Target]:
    """-l > --component > `default` (campaigns, o todos con --notification-id)."""
    if selector:
        return [Target(None, selector)]
    selectors = component_selectors(state.settings)
    if not choices:
        components = default
    elif ComponentChoice.ALL in choices:
        components = list(Component)
    else:
        components = [Component(choice.value) for choice in dict.fromkeys(choices)]
    return [Target(c.value, selectors[c]) for c in components]


def _pods(service: PodsService, targets: list[Target]) -> list[Pod]:
    return [pod for t in targets for pod in service.list_pods(t.selector, t.component)]


def _describe(targets: list[Target]) -> str:
    return ", ".join(t.component or t.selector for t in targets)


@app.command("ls")
def list_(
    ctx: typer.Context, selector: SelectorOption = None, component: ComponentOption = None
) -> None:
    """Lista los pods con su componente, estado, reinicios y nodo."""
    state = get_state(ctx)
    targets = _targets(state, selector, component, [Component.CAMPAIGNS])
    pods = _pods(_service(state), targets)
    render(
        [pod.as_dict() for pod in pods],
        state.output,
        title=f"Pods de {_describe(targets)} en {state.settings.eks_namespace}",
    )


@app.command()
def logs(
    ctx: typer.Context,
    selector: SelectorOption = None,
    component: ComponentOption = None,
    pod: Annotated[
        str | None, typer.Option("--pod", help="Un pod concreto (ignora selector y componente).")
    ] = None,
    container: Annotated[
        str | None,
        typer.Option("--container", "-c", help="Contenedor (por defecto el principal del pod)."),
    ] = None,
    tail: Annotated[
        int | None,
        typer.Option(
            "--tail",
            min=0,
            help=f"Últimas líneas de cada pod (por defecto {DEFAULT_TAIL}; "
            "sin límite con --notification-id).",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help=f"Solo lo de esta ventana: 30m, 2h, 1d ({NOTIFICATION_SINCE} con "
            "--notification-id).",
        ),
    ] = None,
    pattern: Annotated[
        str | None, typer.Option("--filter", help="Solo líneas que contengan este texto.")
    ] = None,
    notification_id: Annotated[
        str | None,
        typer.Option(
            "--notification-id",
            help="Busca este notification_id en campaigns y engine y resume dónde aparece.",
        ),
    ] = None,
    context: Annotated[
        int,
        typer.Option(
            "--context", "-C", min=0, help="Líneas vecinas a mostrar por coincidencia (grep -C)."
        ),
    ] = 0,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Sigue mostrando líneas nuevas (Ctrl+C).")
    ] = False,
    max_pods: Annotated[
        int, typer.Option("--max-pods", min=1, help="Máximo de pods a seguir con -f.")
    ] = 5,
) -> None:
    """Muestra los logs de los pods (como kubectl logs -l ... --tail N)."""
    if notification_id is not None:
        if pattern:
            raise UsageError("Usa --filter o --notification-id, no ambos.")
        pattern = _check_notification_id(notification_id)
        since = since or NOTIFICATION_SINCE
    if context and not pattern:
        raise UsageError("--context requiere --filter o --notification-id.")
    if context and follow:
        raise UsageError("--context no admite --follow.")

    state = get_state(ctx)
    service = _service(state)
    default = list(Component) if notification_id else [Component.CAMPAIGNS]
    targets = _targets(state, selector, component, default)
    pods = [service.get_pod(pod)] if pod else _pods(service, targets)
    if not pods:
        raise TestFailedError(
            f"No hay pods de {_describe(targets)} en el namespace {service.namespace}."
        )
    since_seconds = int(parse_since(since).total_seconds()) if since else None
    if tail is None and notification_id is None:
        tail = DEFAULT_TAIL

    if follow:
        if len(pods) > max_pods:
            raise UsageError(
                f"Hay {len(pods)} pods y --max-pods es {max_pods}: sube --max-pods o usa --pod."
            )
        _follow(state, service, pods, container, tail, since_seconds, pattern)
        return

    lines: list[PodLogLine] = []
    for item in pods:
        lines.extend(
            service.logs(item, container=container, tail=tail, since_seconds=since_seconds)
        )
    selected = (
        select_lines(lines, pattern, context)
        if pattern
        else [SelectedLine(line, False) for line in lines]
    )
    selected.sort(key=lambda s: (s.line.timestamp or datetime.max, s.line.pod))
    summary = (
        summarize(selected, pods, [t.component for t in targets if t.component])
        if notification_id and not pod
        else []
    )
    _print_lines(state, selected, summary, len(pods), with_marks=context > 0)
    if notification_id and not any(s.match for s in selected):
        raise TestFailedError(
            f"El notification_id {notification_id} no aparece en los logs de {_describe(targets)} "
            f"(ventana {since})."
        )


def _check_notification_id(notification_id: str) -> str:
    term = notification_id.strip()
    if len(term) < MIN_TERM_LENGTH:
        raise UsageError(f"El notification_id debe tener al menos {MIN_TERM_LENGTH} caracteres.")
    return term


@app.command()
def scan(
    ctx: typer.Context,
    notification_id: Annotated[str, typer.Argument(help="notification_id a buscar.")],
    component: Annotated[
        list[ComponentChoice] | None,
        typer.Option(
            "--component",
            "-k",
            help="campaigns, engine o all, en el orden de búsqueda (se puede repetir). "
            "Por defecto campaigns y luego engine.",
        ),
    ] = None,
    container: Annotated[
        str | None,
        typer.Option("--container", "-c", help="Contenedor (por defecto el principal del pod)."),
    ] = None,
    since: Annotated[
        str, typer.Option("--since", help="Solo lo de esta ventana: 30m, 2h, 1d.")
    ] = NOTIFICATION_SINCE,
    context: Annotated[
        int,
        typer.Option(
            "--context", "-C", min=0, help="Líneas vecinas a mostrar por coincidencia (grep -C)."
        ),
    ] = 0,
) -> None:
    """Busca un notification_id microservicio por microservicio: un bloque por componente."""
    pattern = _check_notification_id(notification_id)
    state = get_state(ctx)
    service = _service(state)
    targets = _targets(state, None, component, list(Component))
    since_seconds = int(parse_since(since).total_seconds())
    sections: list[dict[str, object]] = []
    found = False
    for target in targets:
        pods = service.list_pods(target.selector, target.component)
        if state.output is not OutputFormat.JSON:
            err_console.rule(f"[magenta]{target.component}[/magenta] ({len(pods)} pod(s))")
        lines: list[PodLogLine] = []
        for found_pod in pods:
            lines.extend(service.logs(found_pod, container=container, since_seconds=since_seconds))
        selected = select_lines(lines, pattern, context)
        selected.sort(key=lambda s: (s.line.timestamp or datetime.max, s.line.pod))
        summary = summarize(selected, pods, [str(target.component)])[0]
        found = found or summary.matches > 0
        if state.output is OutputFormat.JSON:
            rows = [s.as_dict() if context else s.line.as_dict() for s in selected]
            sections.append({**summary.as_dict(), "lineas": rows})
            continue
        for item in selected:
            console.print(_line(item.line, dim=context > 0 and not item.match), highlight=False)
        _print_summary(summary)
    if state.output is OutputFormat.JSON:
        render(sections, state.output)
    if not found:
        raise TestFailedError(
            f"El notification_id {pattern} no aparece en los logs de {_describe(targets)} "
            f"(ventana {since})."
        )


def _print_summary(entry: ComponentSummary) -> None:
    if entry.matches:
        span = (
            f", de {entry.first:%H:%M:%S} a {entry.last:%H:%M:%S}"
            if entry.first and entry.last
            else ""
        )
        info(f"{entry.component}: {entry.matches} coincidencia(s) en {entry.pods} pod(s){span}.")
    else:
        warn(f"{entry.component}: sin coincidencias ({entry.pods} pod(s) revisados).")


def _print_lines(
    state: AppState,
    selected: list[SelectedLine],
    summary: list[ComponentSummary],
    pod_count: int,
    *,
    with_marks: bool,
) -> None:
    if state.output is OutputFormat.JSON:
        rows = [s.as_dict() if with_marks else s.line.as_dict() for s in selected]
        if summary:
            render({"lineas": rows, "resumen": [s.as_dict() for s in summary]}, state.output)
        else:
            render(rows, state.output)
        return
    if not selected:
        info("Sin líneas de log para los pods consultados.")
    for item in selected:
        console.print(_line(item.line, dim=with_marks and not item.match), highlight=False)
    if selected:
        info(f"{len(selected)} línea(s) de {pod_count} pod(s). Horas en hora Colombia.")
    for entry in summary:
        _print_summary(entry)


def _matches(line: PodLogLine, pattern: str | None) -> bool:
    return not pattern or pattern in line.message


def _follow(
    state: AppState,
    service: PodsService,
    pods: list[Pod],
    container: str | None,
    tail: int | None,
    since_seconds: int | None,
    pattern: str | None,
) -> None:
    names = ", ".join(pod.name for pod in pods)
    info(f"Siguiendo {len(pods)} pod(s): {names} (Ctrl+C para salir)...")
    stop = threading.Event()
    try:
        for item in service.follow_many(
            pods, stop, container=container, tail=tail, since_seconds=since_seconds
        ):
            if isinstance(item, StreamEnd):
                warn(f"{item.pod}: {item.reason}")
            elif not _matches(item, pattern):
                continue
            elif state.output is OutputFormat.JSON:
                console.out(to_json(item.as_dict()).replace("\n", " "), highlight=False)
            else:
                console.print(_line(item), highlight=False)
    except KeyboardInterrupt:
        info("Seguimiento detenido.")
    finally:
        stop.set()


def _line(line: PodLogLine, *, dim: bool = False) -> str:
    when = f"{line.timestamp:%Y-%m-%d %H:%M:%S}" if line.timestamp else "-"
    prefix = f"[magenta]{escape(f'[{line.component}]')}[/magenta] " if line.component else ""
    message = escape(line.message)
    if dim:
        message = f"[dim]{message}[/dim]"
    return f"{prefix}[cyan]{escape(line.pod)}[/cyan] [dim]{when}[/dim]  {message}"
