"""Excepciones de la CLI, códigos de salida y traducción de errores de AWS y HTTP a mensajes."""

from enum import IntEnum

import httpx
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
    PartialCredentialsError,
    ProfileNotFound,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from campaigns_cli.settings import Settings, SettingsError


class ExitCode(IntEnum):
    OK = 0
    TEST_FAILED = 1
    USAGE = 2
    AWS = 3  # AWS o servicio externo (Cognito, fake channel)


class CliError(Exception):
    """Error esperado: se muestra como mensaje corto, sin traceback."""

    exit_code: ExitCode = ExitCode.USAGE


class UsageError(CliError):
    exit_code = ExitCode.USAGE


class TestFailedError(CliError):
    __test__ = False  # evita que pytest la tome como clase de pruebas
    exit_code = ExitCode.TEST_FAILED


class AwsError(CliError):
    exit_code = ExitCode.AWS


class ExternalServiceError(CliError):
    """Error de un servicio externo por HTTP (Cognito, fake channel). Mismo código que AWS."""

    exit_code = ExitCode.AWS


class ServiceAuthError(ExternalServiceError):
    """El servicio rechazó las credenciales o el token (HTTP 400/401/403)."""


ACCESS_DENIED_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "AuthorizationError",
        "403",
    }
)
NOT_FOUND_CODES = frozenset(
    {
        "ResourceNotFoundException",
        "NoSuchBucket",
        "NoSuchKey",
        "NotFound",
        "404",
    }
)
EXPIRED_CREDENTIALS_CODES = frozenset(
    {
        "ExpiredToken",
        "ExpiredTokenException",
        "InvalidClientTokenId",
        "UnrecognizedClientException",
    }
)

CREDENTIALS_ERRORS = (
    NoCredentialsError,
    PartialCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)


def client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def is_not_found(exc: ClientError) -> bool:
    return client_error_code(exc) in NOT_FOUND_CODES


def is_access_denied(exc: ClientError) -> bool:
    return client_error_code(exc) in ACCESS_DENIED_CODES


def _credentials_hint(settings: Settings | None) -> str:
    if settings is not None and settings.aws_profile and not settings.has_static_credentials:
        return f"Revisa el perfil `{settings.aws_profile}` (AWS_PROFILE) o su sesión SSO."
    return (
        "Revisa AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y AWS_SESSION_TOKEN en el .env "
        "(las credenciales temporales vencen)."
    )


def translate(exc: BaseException, settings: Settings | None = None) -> tuple[str, ExitCode] | None:
    """Convierte una excepción conocida en (mensaje, exit code). None si no es conocida."""
    profile = settings.aws_profile if settings else None
    if isinstance(exc, CliError):
        return str(exc), exc.exit_code
    if isinstance(exc, SettingsError):
        return str(exc), ExitCode.USAGE
    if isinstance(exc, CREDENTIALS_ERRORS):
        return f"Sin credenciales AWS válidas. {_credentials_hint(settings)}", ExitCode.AWS
    if isinstance(exc, ProfileNotFound):
        return f"No existe el perfil AWS `{profile}` en ~/.aws/config.", ExitCode.AWS
    if isinstance(exc, NoRegionError):
        return "No hay región AWS configurada. Define AWS_REGION en el .env.", ExitCode.AWS
    if isinstance(exc, EndpointConnectionError):
        return f"No se pudo conectar con AWS: {exc}", ExitCode.AWS
    if isinstance(exc, ClientError):
        code = client_error_code(exc)
        operation = exc.operation_name
        message = exc.response.get("Error", {}).get("Message", "") or code
        if code in EXPIRED_CREDENTIALS_CODES:
            message = f"Credenciales AWS vencidas o inválidas. {_credentials_hint(settings)}"
            return message, ExitCode.AWS
        if code in ACCESS_DENIED_CODES:
            return f"Permiso denegado en `{operation}`: {message}", ExitCode.AWS
        if code in NOT_FOUND_CODES:
            return f"No existe el recurso solicitado en `{operation}`: {message}", ExitCode.AWS
        return f"Error de AWS en `{operation}` ({code}): {message}", ExitCode.AWS
    if isinstance(exc, BotoCoreError):
        return f"Error de AWS: {exc}", ExitCode.AWS
    if isinstance(exc, httpx.TimeoutException):
        return f"El servicio no respondió a tiempo ({_request_url(exc)}).", ExitCode.AWS
    if isinstance(exc, httpx.TransportError):
        return f"No se pudo conectar con {_request_url(exc)}: {exc}", ExitCode.AWS
    return None


def _request_url(exc: httpx.TransportError) -> str:
    try:
        return str(exc.request.url.copy_with(query=None))
    except RuntimeError:
        return "el servicio"
