from campaigns_cli.aws import AwsClients
from campaigns_cli.settings import Settings


def test_session_uses_env_file_credentials() -> None:
    settings = Settings(
        aws_access_key_id="AKIAEJEMPLO",
        aws_secret_access_key="secreto",
        aws_session_token="token",
        aws_profile="perfil-ignorado",
        aws_region="us-east-2",
    )

    session = AwsClients(settings).session
    credentials = session.get_credentials()

    assert credentials is not None
    assert credentials.access_key == "AKIAEJEMPLO"
    assert credentials.secret_key == "secreto"
    assert credentials.token == "token"
    assert session.region_name == "us-east-2"


def test_clients_are_created_lazily_and_cached() -> None:
    clients = AwsClients(Settings(aws_access_key_id="AKIA", aws_secret_access_key="s"))

    assert "session" not in clients.__dict__
    assert clients.s3 is clients.s3
    assert clients.s3.meta.region_name == "us-east-1"
