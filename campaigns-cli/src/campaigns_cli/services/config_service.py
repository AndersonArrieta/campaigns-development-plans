"""Verificación de credenciales y existencia de los recursos configurados."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from campaigns_cli.errors import client_error_code, is_access_denied, is_not_found
from campaigns_cli.settings import Settings, env_var_name

if TYPE_CHECKING:
    from mypy_boto3_sts import STSClient

    from campaigns_cli.aws import AwsClients


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
    if not settings.campaigns_log_groups:
        return [_missing("Log group", "campaigns_log_groups")]

    checks = []
    variable = env_var_name("campaigns_log_groups")
    for group in settings.campaigns_log_groups:
        status, detail, exists = _probe(partial(_log_group_exists, aws, group))
        if status is Status.OK and not exists:
            status = Status.NOT_FOUND
        checks.append(ResourceCheck("Log group", variable, group, status, detail))
    return checks


def check_resources(settings: Settings, aws: AwsClients) -> list[ResourceCheck]:
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

    for field in ("ingester_lambda_name", "scheduler_lambda_name"):
        name = getattr(settings, field)
        if not name:
            checks.append(_missing("Lambda", field))
            continue
        status, detail, _ = _probe(partial(aws.lambda_.get_function, FunctionName=name))
        checks.append(ResourceCheck("Lambda", env_var_name(field), name, status, detail))

    checks.extend(_check_log_groups(settings, aws))
    return checks
