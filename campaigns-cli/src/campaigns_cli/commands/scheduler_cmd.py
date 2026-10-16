"""Comandos `scheduler`: invocan scheduler_Lambda a demanda (bloqueados en prod)."""

from typing import Annotated

import typer

from campaigns_cli.errors import AwsError, TestFailedError
from campaigns_cli.guards import confirm_destructive, ensure_not_prod
from campaigns_cli.output import console, info, render, success, warn
from campaigns_cli.services.dynamo_service import CampaignsTable
from campaigns_cli.services.lambda_service import InvokeResult, LambdaService
from campaigns_cli.services.logs_service import LogsService
from campaigns_cli.services.scheduler_service import (
    Outcome,
    Preview,
    RunResult,
    SchedulerService,
    detail_of,
    health_ok,
)
from campaigns_cli.settings import OutputFormat
from campaigns_cli.state import AppState, get_state

app = typer.Typer(
    help="Invoca scheduler_Lambda a demanda, sin reintentos que la re-ejecuten.",
    no_args_is_help=True,
)

TailOption = Annotated[
    bool, typer.Option("--tail", help="Muestra los últimos 4 KB del log de la ejecución.")
]


def _service(state: AppState, *, with_table: bool) -> SchedulerService:
    settings = state.settings
    settings.require("scheduler_lambda_name", *(("campaigns_table_name",) if with_table else ()))
    aws = state.aws
    table = None
    if with_table:
        table = CampaignsTable(
            aws.dynamodb,
            str(settings.campaigns_table_name),
            settings.campaigns_table_campaign_index,
        )
    return SchedulerService(
        LambdaService(aws.lambda_, aws.lambda_invoke_client),
        str(settings.scheduler_lambda_name),
        table=table,
        logs=LogsService(aws.logs),
        log_group=settings.lambda_log_groups.get("scheduler"),
        test_app_id=settings.cli_test_app_id,
    )


def _show_preview(state: AppState, preview: Preview) -> None:
    info(
        f"Partición en curso: {preview.partition} (hora Colombia), "
        f"{preview.total} fila(s) en la tabla de campañas."
    )
    if state.output is OutputFormat.TABLE and preview.total:
        render(preview.rows(), state.output, title=f"Filas de {preview.partition} por app_id")
    if preview.other_apps:
        warn(
            f"Hay filas de otros app_id ({', '.join(preview.other_apps)}): se reenviarán "
            "notificaciones de otros equipos."
        )
    if not preview.total:
        warn(
            "La partición está vacía: el scheduler no enviará nada "
            "(sirve para probar la invocación)."
        )


def _invocation_rows(invocation: InvokeResult) -> dict[str, object]:
    detail = detail_of(invocation.payload)
    return {
        "funcion": invocation.function,
        "status_code": invocation.status_code,
        "function_error": invocation.function_error,
        "executed_version": invocation.executed_version,
        "request_id": invocation.request_id,
        "intentos": invocation.attempts,
        "total": detail.get("total"),
        "successful": detail.get("successful"),
        "failed": detail.get("failed"),
        "error": invocation.error,
    }


def _show_tail(invocation: InvokeResult) -> None:
    if invocation.log_tail:
        info("Últimos 4 KB del log de la ejecución:")
        console.out(invocation.log_tail.rstrip("\n"), highlight=False)


@app.command()
def run(
    ctx: typer.Context,
    tail: TailOption = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Omite la confirmación.")] = False,
) -> None:
    """Invoca el scheduler una vez: reenvía a Kafka todas las filas de la hora en curso."""
    state = get_state(ctx)
    settings = state.settings
    ensure_not_prod(settings, "scheduler run")
    service = _service(state, with_table=True)
    if yes:
        state.assume_yes = True

    preview = service.preview()
    _show_preview(state, preview)
    confirm_destructive(
        state,
        f"¿Invocar {service.function_name} en {settings.campaigns_env}? Reenviará a Kafka "
        f"{preview.total} notificación(es) de la partición {preview.partition}.",
    )
    result = service.run(preview, tail=tail)
    _report_run(state, result)


def _report_run(state: AppState, result: RunResult) -> None:
    invocation = result.invocation
    if result.partition_changed:
        warn(
            f"La hora cambió entre la vista previa y la invocación: el scheduler procesó "
            f"{result.partition_at_invoke}, no {result.preview.partition}."
        )
    if state.output is OutputFormat.JSON:
        render(result.as_dict(), state.output)
    else:
        render(_invocation_rows(invocation), state.output, title="Resultado de scheduler run")
        _show_tail(invocation)
        if result.log_hits:
            render(
                [{"hora": hit.timestamp, "mensaje": hit.message} for hit in result.log_hits],
                state.output,
                title="Execution result en el log del scheduler",
            )

    outcome = result.outcome
    if outcome is Outcome.DESCONOCIDO:
        found = (
            "aparece un `Execution result` posterior a la invocación (ver arriba)"
            if result.log_hits
            else "no aparece aún un `Execution result` en su log; revisa `logs tail -l scheduler`"
        )
        raise AwsError(
            f"Resultado DESCONOCIDO ({invocation.error}): la Lambda pudo haber corrido y no se "
            f"reintentó; {found}."
        )
    if outcome is Outcome.FALLA:
        if invocation.function_error:
            payload = invocation.payload
            message = payload.get("errorMessage") if isinstance(payload, dict) else payload
            reason = f"FunctionError={invocation.function_error}: {message}"
        else:
            reason = f"{detail_of(invocation.payload).get('failed')} notificación(es) fallidas"
        raise TestFailedError(f"El scheduler terminó con errores: {reason}.")
    success("Scheduler ejecutado una vez.")


@app.command()
def health(ctx: typer.Context, tail: TailOption = False) -> None:
    """Invoca con {"type": "health"}: prueba la conexión a Kafka sin despachar nada."""
    state = get_state(ctx)
    ensure_not_prod(state.settings, "scheduler health")
    invocation = _service(state, with_table=False).health(tail=tail)
    ok = health_ok(invocation)
    if state.output is OutputFormat.JSON:
        render({"invocation": invocation.as_dict(), "kafka_ok": ok}, state.output)
    else:
        render(
            {**_invocation_rows(invocation), "kafka_ok": ok},
            state.output,
            title="Resultado de scheduler health",
        )
        _show_tail(invocation)
    if invocation.unknown:
        raise AwsError(f"Resultado DESCONOCIDO ({invocation.error}).")
    if not ok:
        raise TestFailedError("Kafka no responde según el health check del scheduler.")
    success("Kafka responde.")
