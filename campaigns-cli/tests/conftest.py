from collections.abc import Iterator
from pathlib import Path

import pytest
from moto import mock_aws

from campaigns_cli.settings import Settings, env_var_name

AWS_CREDENTIAL_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_DEFAULT_PROFILE",
    "AWS_DEFAULT_REGION",
)


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Aísla cada prueba del .env real, de las variables del proceso y de ~/.aws."""
    for field in Settings.model_fields:
        monkeypatch.delenv(env_var_name(field), raising=False)
    for name in AWS_CREDENTIAL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "aws-config-inexistente"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "aws-creds-inexistente"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture
def write_env(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _write(content: str, name: str = ".env") -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credenciales falsas: nunca se llega a la cuenta real."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mocked_aws(aws_credentials: None) -> Iterator[None]:
    with mock_aws():
        yield
