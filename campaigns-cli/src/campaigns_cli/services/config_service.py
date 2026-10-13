"""Verificación de credenciales y existencia de los recursos configurados (AWS y fake channel)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING

import httpx
from botocore.exceptions import ClientError

from campaigns_cli.errors import (
    ExternalServiceError,
    ServiceAuthError,
    client_error_code,
    is_access_denied,
    is_not_found,
)
from campaigns_cli.services.channel_service import (
    REQUIRED_SETTINGS as CHANNEL_SETTINGS,
)
from campaigns_cli.services.channel_service import (
    Channel,
    fake_channel_from,
)
from campaigns_cli.services.k8s_service import REQUIRED_SETTINGS as EKS_SETTINGS
from campaigns_cli.services.k8s_service import component_selectors, pods_service_from
from campaigns_cli.settings import Settings, env_var_name

if TYPE_CHECKING:
    from mypy_boto3_sts import STSClient

    from campaigns_cli.aws import AwsClients
    from campaigns_cli.http import HttpClients


class Status(StrEnum):
    OK = "OK"
    MISSING_CONFIG = "FALTA CONFIG"
    NOT_FOUND = "NO EXISTE"
    ACCESS_DENIED = "SIN PERMISO"
    ERROR = "ERROR"
    OPTIONAL = "OPCIONAL"


@dataclass(frozen=True)
class ResourceCheck:
    recurso: str
    variable: str
    nombre: str
    estado: Status
    detalle: str = ""

    @property
    def failed(self) -> bool:
        return self.estado not in (Status.OK, Status.OPTIONAL)

    def as_dict(self) -> dict[str, str]:
        return {
            "recurso": self.recurso,
            "variable": self.variable,
            "nombre": self.nombre,
            "estado": self.estado.value,
            "detalle": self.detalle,
        }


def get_identity(sts: STSClient) -> dict[str, str]:
    identity = sts.get_caller_identity()
    return {"cuenta": identity["Account"], "arn": identity["Arn"]}


def _probe[T](call: Callable[[], T]) -> tuple[Status, str, T | None]:
    """Ejecuta una llamada de lectura y clasifica el resultado.

    Los errores de credenciales no se capturan: se propagan y terminan con exit code 3.
    """
    try:
        result = call()
    except ClientError as exc:
        if is_not_found(exc):
            return Status.NOT_FOUND, "", None
        if is_access_denied(exc):
            return Status.ACCESS_DENIED, exc.operation_name, None
        return Status.ERROR, f"{client_error_code(exc)}: {exc}", None
    return Status.OK, "", result


def _missing(recurso: str, field: str, optional: bool = False) -> ResourceCheck:
    status = Status.OPTIONAL if optional else Status.MISSING_CONFIG
    return ResourceCheck(recurso, env_var_name(field), "", status)


def _check_table(settings: Settings, aws: AwsClients) -> list[ResourceCheck]:
    table = settings.campaigns_table_name
    index = settings.campaigns_table_campaign_index
    if not table:
        return [
            _missing("DynamoDB tabla", "campaigns_table_name"),
            _missing("DynamoDB GSI", "campaigns_table_campaign_index", optional=True),
        ]

    status, detail, description = _probe(
        lambda: aws.dynamodb.describe_table(TableName=table)["Table"]
    )
    checks = [
        ResourceCheck("DynamoDB tabla", env_var_name("campaigns_table_name"), table, status, detail)
    ]
    index_var = env_var_name("campaigns_table_campaign_index")
    if not index:
        checks.append(
            ResourceCheck(
                "DynamoDB GSI", index_var, "", Status.OPTIONAL, "sin GSI: búsquedas con scan"
            )
        )
    elif description is None:
        checks.append(
            ResourceCheck(
                "DynamoDB GSI", index_var, index, Status.ERROR, "no se pudo leer la tabla"
            )
        )
    else:
        names = {gsi.get("IndexName") for gsi in description.get("GlobalSecondaryIndexes", [])}
        found = Status.OK if index in names else Status.NOT_FOUND
        checks.append(ResourceCheck("DynamoDB GSI", index_var, index, found))
    return checks


def _log_group_exists(aws: AwsClients, group: str) -> bool:
    pages = aws.logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=group)
    return any(lg["logGroupName"] == group for page in pages for lg in page["logGroups"])


def _check_log_groups(settings: Settings, aws: AwsClients) -> list[ResourceCheck]:
    groups = settings.effective_log_groups
    if not groups:
        return [_missing("Log group", "campaigns_log_groups")]

    checks = []
    variable = env_var_name("campaigns_log_groups")
    if not settings.campaigns_log_groups:
        variable += " (derivado de las lambdas)"
    for group in groups:
        status, detail, exists = _probe(partial(_log_group_exists, aws, group))
        if status is Status.OK and not exists:
            status = Status.NOT_FOUND
        checks.append(ResourceCheck("Log group", variable, group, status, detail))
    return checks


# Usuario que no existe: el fake channel debe responder 404 "No messages found".
PROBE_USER = "0000000000"


def _probe_http[T](call: Callable[[], T]) -> tuple[Status, str]:
    try:
        call()
    except ServiceAuthError as exc:
        return Status.ACCESS_DENIED, str(exc)
    except (ExternalServiceError, httpx.TransportError) as exc:
        return Status.ERROR, str(exc)
    return Status.OK, ""


def _check_channel(settings: Settings, http: HttpClients) -> list[ResourceCheck]:
    """Cognito y fake channel son opcionales: solo los usa el grupo `channel`."""
    token_var = env_var_name("cognito_token_url")
    base_var = env_var_name("fake_channel_base_url")
    missing = [env_var_name(name) for name in CHANNEL_SETTINGS if not getattr(settings, name)]
    if len(missing) == len(CHANNEL_SETTINGS):
        detail = "sin configurar: el grupo channel no está disponible"
        return [
            ResourceCheck("Cognito", token_var, "", Status.OPTIONAL, detail),
            ResourceCheck("Fake channel", base_var, "", Status.OPTIONAL, detail),
        ]
    if missing:
        detail = "falta " + ", ".join(missing)
        return [
            ResourceCheck("Cognito", token_var, "", Status.MISSING_CONFIG, detail),
            ResourceCheck("Fake channel", base_var, "", Status.MISSING_CONFIG, detail),
        ]

    channel = fake_channel_from(settings, http)
    status, detail = _probe_http(channel.auth.token)
    checks = [ResourceCheck("Cognito", token_var, channel.auth.url, status, detail)]
    if status is not Status.OK:
        checks.append(
            ResourceCheck(
                "Fake channel", base_var, channel.base_url, Status.ERROR, "sin token de Cognito"
            )
        )
        return checks
    status, detail = _probe_http(lambda: channel.messages(Channel.WHATSAPP, PROBE_USER))
    checks.append(ResourceCheck("Fake channel", base_var, channel.base_url, status, detail))
    return checks


def _check_eks(settings: Settings, aws: AwsClients, http: HttpClients) -> ResourceCheck:
    """EKS es opcional: solo lo usa el grupo `pods`."""
    variable = env_var_name("eks_cluster_name")
    missing = [env_var_name(name) for name in EKS_SETTINGS if not getattr(settings, name)]
    if len(missing) == len(EKS_SETTINGS):
        detail = "sin configurar: el grupo pods no está disponible"
        return ResourceCheck("EKS", variable, "", Status.OPTIONAL, detail)
    if missing:
        return ResourceCheck(
            "EKS", variable, "", Status.MISSING_CONFIG, "falta " + ", ".join(missing)
        )

    name = f"{settings.eks_cluster_name}/{settings.eks_namespace}"
    try:
        service = pods_service_from(settings, aws, http)
        counts = {
            component: len(service.list_pods(selector))
            for component, selector in component_selectors(settings).items()
        }
    except ClientError as exc:
        if is_not_found(exc):
            return ResourceCheck("EKS", variable, name, Status.NOT_FOUND)
        if is_access_denied(exc):
            return ResourceCheck("EKS", variable, name, Status.ACCESS_DENIED, exc.operation_name)
        return ResourceCheck(
            "EKS", variable, name, Status.ERROR, f"{client_error_code(exc)}: {exc}"
        )
    except ServiceAuthError as exc:
        return ResourceCheck("EKS", variable, name, Status.ACCESS_DENIED, str(exc))
    except (ExternalServiceError, httpx.TransportError) as exc:
        return ResourceCheck("EKS", variable, name, Status.ERROR, str(exc))
    detail = ", ".join(f"{count} pod(s) {component}" for component, count in counts.items())
    if not all(counts.values()):
        detail += " (un componente sin pods: ¿escalado a 0?)"
    return ResourceCheck("EKS", variable, name, Status.OK, detail)


def check_resources(settings: Settings, aws: AwsClients, http: HttpClients) -> list[ResourceCheck]:
    checks: list[ResourceCheck] = []

    bucket = settings.campaigns_input_bucket
    if bucket:
        status, detail, _ = _probe(lambda: aws.s3.head_bucket(Bucket=bucket))
        checks.append(
            ResourceCheck(
                "S3 bucket", env_var_name("campaigns_input_bucket"), bucket, status, detail
            )
        )
    else:
        checks.append(_missing("S3 bucket", "campaigns_input_bucket"))

    checks.extend(_check_table(settings, aws))

    logs_table = settings.campaigns_logs_table_name
    if logs_table:
        status, detail, _ = _probe(partial(aws.dynamodb.describe_table, TableName=logs_table))
        checks.append(
            ResourceCheck(
                "DynamoDB logs",
                env_var_name("campaigns_logs_table_name"),
                logs_table,
                status,
                detail,
            )
        )
    else:
        checks.append(_missing("DynamoDB logs", "campaigns_logs_table_name"))

    for field in ("ingester_lambda_name", "scheduler_lambda_name"):
        name = getattr(settings, field)
        if not name:
            checks.append(_missing("Lambda", field))
            continue
        status, detail, _ = _probe(partial(aws.lambda_.get_function, FunctionName=name))
        checks.append(ResourceCheck("Lambda", env_var_name(field), name, status, detail))

    checks.extend(_check_log_groups(settings, aws))
    checks.extend(_check_channel(settings, http))
    checks.append(_check_eks(settings, aws, http))
    return checks
