"""Comandos `pods`: logs de los pods de platform_campaigns_ms en EKS (solo lectura)."""

import threading
from datetime import datetime
from typing import Annotated

import typer
from rich.markup import escape

from campaigns_cli.errors import TestFailedError, UsageError
from campaigns_cli.output import console, info, render, to_json, warn
from campaigns_cli.services.k8s_service import (
    Pod,
    PodLogLine,
    PodsService,
    StreamEnd,
    pods_service_from,
)
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState, get_state
from campaigns_cli.timeutils import parse_since

app = typer.Typer(
    help="Logs de los pods de platform_campaigns_ms en EKS (solo lectura, hora Colombia).",
    no_args_is_help=True,
)

SelectorOption = Annotated[
    str | None,
    typer.Option(
        "--selector", "-l", help="Selector de etiquetas (por defecto CAMPAIGNS_POD_SELECTOR)."
    ),
]


def _service(state: AppState) -> PodsService:
    return pods_service_from(state.settings, state.aws, state.http)


def _selector(state: AppState, selector: str | None) -> str:
    return selector or state.settings.campaigns_pod_selector


@app.command("ls")
def list_(ctx: typer.Context, selector: SelectorOption = None) -> None:
    """Lista los pods del selector con su estado, reinicios y nodo."""
    state = get_state(ctx)
    chosen = _selector(state, selector)
    pods = _service(state).list_pods(chosen)
    render(
        [pod.as_dict() for pod in pods],
        state.output,
        title=f"Pods con {chosen} en {state.settings.eks_namespace}",
    )


@app.command()
def logs(
    ctx: typer.Context,
    selector: SelectorOption = None,
    pod: Annotated[
        str | None, typer.Option("--pod", help="Un pod concreto (ignora el selector).")
    ] = None,
    container: Annotated[
        str | None,
        typer.Option("--container", "-c", help="Contenedor (por defecto el principal del pod)."),
    ] = None,
    tail: Annotated[int, typer.Option("--tail", min=0, help="Últimas líneas de cada pod.")] = 1000,
    since: Annotated[
        str | None, typer.Option("--since", help="Solo lo de esta ventana: 30m, 2h, 1d.")
    ] = None,
    pattern: Annotated[
        str | None, typer.Option("--filter", help="Solo líneas que contengan este texto.")
    ] = None,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Sigue mostrando líneas nuevas (Ctrl+C).")
    ] = False,
    max_pods: Annotated[
        int, typer.Option("--max-pods", min=1, help="Máximo de pods a seguir con -f.")
    ] = 5,
) -> None:
    """Muestra los logs de los pods del microservicio (como kubectl logs -l ... --tail N)."""
    state = get_state(ctx)
    service = _service(state)
    chosen = _selector(state, selector)
    pods = [service.get_pod(pod)] if pod else service.list_pods(chosen)
    if not pods:
        raise TestFailedError(f"No hay pods con {chosen} en el namespace {service.namespace}.")
    since_seconds = int(parse_since(since).total_seconds()) if since else None

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
    lines = [line for line in lines if _matches(line, pattern)]
    lines.sort(key=lambda line: (line.timestamp or datetime.max, line.pod))
    if state.output is OutputFormat.JSON:
        render([line.as_dict() for line in lines], state.output)
        return
    if not lines:
        info("Sin líneas de log para los pods consultados.")
        return
    for line in lines:
        console.print(_line(line), highlight=False)
    info(f"{len(lines)} línea(s) de {len(pods)} pod(s). Horas en hora Colombia.")


def _matches(line: PodLogLine, pattern: str | None) -> bool:
    return not pattern or pattern in line.message


def _follow(
    state: AppState,
    service: PodsService,
    pods: list[Pod],
    container: str | None,
    tail: int,
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


def _line(line: PodLogLine) -> str:
    when = f"{line.timestamp:%Y-%m-%d %H:%M:%S}" if line.timestamp else "-"
    return f"[cyan]{escape(line.pod)}[/cyan] [dim]{when}[/dim]  {escape(line.message)}"
