"""Fábrica de sesión y clientes boto3 a partir de Settings."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from campaigns_cli.settings import Settings

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_eks import EKSClient
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_logs import CloudWatchLogsClient
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_sts import STSClient

CLIENT_CONFIG = Config(retries={"mode": "standard", "max_attempts": 5})


class AwsClients:
    """Crea la sesión y los clientes solo cuando se piden por primera vez.

    Así los comandos que no tocan AWS (`csv`, `config show`) no requieren credenciales.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def session(self) -> boto3.Session:
        """Credenciales del .env si existen; si no, AWS_PROFILE o la cadena estándar de boto3."""
        settings = self.settings
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            token = settings.aws_session_token
            return boto3.Session(
                aws_access_key_id=settings.aws_access_key_id.get_secret_value(),
                aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
                aws_session_token=token.get_secret_value() if token else None,
                region_name=settings.aws_region,
            )
        return boto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region,
        )

    @cached_property
    def s3(self) -> S3Client:
        return self.session.client("s3", config=CLIENT_CONFIG)

    @cached_property
    def dynamodb(self) -> DynamoDBClient:
        return self.session.client("dynamodb", config=CLIENT_CONFIG)

    @cached_property
    def eks(self) -> EKSClient:
        return self.session.client("eks", config=CLIENT_CONFIG)

    @cached_property
    def lambda_(self) -> LambdaClient:
        return self.session.client("lambda", config=CLIENT_CONFIG)

    @cached_property
    def logs(self) -> CloudWatchLogsClient:
        return self.session.client("logs", config=CLIENT_CONFIG)

    @cached_property
    def sts(self) -> STSClient:
        return self.session.client("sts", config=CLIENT_CONFIG)
