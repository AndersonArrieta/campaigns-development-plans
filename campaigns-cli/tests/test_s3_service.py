from datetime import datetime
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError

from campaigns_cli.errors import UsageError
from campaigns_cli.services.s3_service import S3Service, normalize_prefix

REGION = "us-east-1"
BUCKET = "campaigns-data-test"
NOW = datetime(2026, 10, 16, 9, 30)

pytestmark = pytest.mark.usefixtures("mocked_aws")


@pytest.fixture
def client():  # type: ignore[no-untyped-def]
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket=BUCKET)
    return s3


def _service(client, prefix: str = "") -> S3Service:  # type: ignore[no-untyped-def]
    return S3Service(client, BUCKET, prefix, clock=lambda: NOW)


def test_normalize_prefix() -> None:
    assert normalize_prefix("") == ""
    assert normalize_prefix("  ") == ""
    assert normalize_prefix("entrada") == "entrada/"
    assert normalize_prefix("/entrada/") == "entrada/"


def test_upload_uses_prefix_and_text_csv(client, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "campaign.csv"
    path.write_text("app_id;canal\n", encoding="utf-8")

    result = _service(client, "entrada").upload(path)

    assert result.key == "entrada/campaign.csv"
    assert result.etag and '"' not in result.etag
    assert result.uploaded_at == NOW
    head = client.head_object(Bucket=BUCKET, Key="entrada/campaign.csv")
    assert head["ContentType"] == "text/csv"


def test_upload_with_explicit_key_and_versioning(client, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    client.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
    path = tmp_path / "c.csv"
    path.write_text("x\n", encoding="utf-8")

    result = _service(client).upload(path, "otra/clave.csv")

    assert result.key == "otra/clave.csv"
    assert result.version_id


def test_list_returns_all_pages_newest_first(client) -> None:  # type: ignore[no-untyped-def]
    for index in range(1005):
        client.put_object(Bucket=BUCKET, Key=f"entrada/{index:04d}.csv", Body=b"x")
    client.put_object(Bucket=BUCKET, Key="fuera.csv", Body=b"x")
    service = _service(client, "entrada")

    objects, truncated = service.list()
    limited, limited_truncated = service.list(limit=10)
    everything, _ = service.list(prefix="")

    assert len(objects) == 1005 and not truncated
    assert len(limited) == 10 and limited_truncated
    assert len(everything) == 1006
    assert [obj.last_modified for obj in objects] == sorted(
        (obj.last_modified for obj in objects), reverse=True
    )


def test_download(client) -> None:  # type: ignore[no-untyped-def]
    client.put_object(Bucket=BUCKET, Key="a.csv", Body=b"hola")

    assert _service(client).download("a.csv") == b"hola"


def test_delete_only_inside_prefix(client) -> None:  # type: ignore[no-untyped-def]
    client.put_object(Bucket=BUCKET, Key="entrada/a.csv", Body=b"x")
    client.put_object(Bucket=BUCKET, Key="otro/a.csv", Body=b"x")
    service = _service(client, "entrada")

    with pytest.raises(UsageError, match="fuera de CAMPAIGNS_INPUT_PREFIX"):
        service.delete("otro/a.csv")
    service.delete("entrada/a.csv")

    keys = [item["Key"] for item in client.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert keys == ["otro/a.csv"]


def test_delete_missing_key_fails(client) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ClientError):
        _service(client).delete("no-existe.csv")
