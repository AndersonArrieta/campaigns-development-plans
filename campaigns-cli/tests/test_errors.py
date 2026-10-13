import pytest
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

from campaigns_cli.errors import (
    ExitCode,
    TestFailedError,
    UsageError,
    is_access_denied,
    is_not_found,
    translate,
)
from campaigns_cli.settings import MissingSettingError, Settings


def _client_error(code: str, operation: str = "DescribeTable") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": f"mensaje {code}"}}, operation)


def test_cli_errors_keep_their_exit_code() -> None:
    assert translate(UsageError("uso")) == ("uso", ExitCode.USAGE)
    assert translate(TestFailedError("falla")) == ("falla", ExitCode.TEST_FAILED)


def test_missing_setting_is_usage_error() -> None:
    message, code = translate(MissingSettingError(["CAMPAIGNS_TABLE_NAME"])) or ("", None)

    assert code is ExitCode.USAGE
    assert "CAMPAIGNS_TABLE_NAME" in message


def test_no_credentials_points_to_env_file() -> None:
    message, code = translate(NoCredentialsError(), Settings()) or ("", None)

    assert code is ExitCode.AWS
    assert "AWS_ACCESS_KEY_ID" in message
    assert ".env" in message


def test_no_credentials_with_profile_points_to_profile() -> None:
    message, _ = translate(NoCredentialsError(), Settings(aws_profile="dev")) or ("", None)

    assert "`dev`" in message


def test_expired_token_points_to_env_file() -> None:
    settings = Settings(aws_access_key_id="AKIA", aws_secret_access_key="s", aws_profile="dev")

    message, _ = translate(_client_error("ExpiredTokenException"), settings) or ("", None)

    assert "AWS_SESSION_TOKEN" in message


def test_profile_not_found() -> None:
    message, code = translate(ProfileNotFound(profile="x"), Settings(aws_profile="x")) or ("", None)

    assert code is ExitCode.AWS
    assert "`x`" in message


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("AccessDeniedException", "Permiso denegado en `DescribeTable`"),
        ("ResourceNotFoundException", "No existe el recurso"),
        ("ExpiredTokenException", "Credenciales AWS vencidas"),
        ("ThrottlingException", "Error de AWS en `DescribeTable` (ThrottlingException)"),
    ],
)
def test_client_errors(code: str, expected: str) -> None:
    message, exit_code = translate(_client_error(code)) or ("", None)

    assert exit_code is ExitCode.AWS
    assert expected in message


def test_unknown_exception_is_not_translated() -> None:
    assert translate(ValueError("bug")) is None


def test_error_classifiers() -> None:
    assert is_not_found(_client_error("NoSuchBucket"))
    assert is_not_found(_client_error("404"))
    assert is_access_denied(_client_error("403"))
    assert not is_not_found(_client_error("AccessDenied"))
