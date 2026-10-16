import json
from pathlib import Path
from typing import Any

import boto3
import pytest
from typer.testing import CliRunner

from campaigns_cli.commands import s3_cmd
from campaigns_cli.main import app

runner = CliRunner(env={"COLUMNS": "250"})

REGION = "us-east-1"
BUCKET = "campaigns-data-test"
FIXTURE = Path(__file__).parent / "fixtures" / "csv-test.csv"
ENV = f"AWS_REGION={REGION}\nCAMPAIGNS_INPUT_BUCKET={BUCKET}\n"
INVALID_CSV = (
    "app_id;canal;usuario;fecha_inicio;fecha_fin;dias;horas;nodo;parametros\n"
    "others-test;WhatsApp;573232540390;25/12/2099;25/12/2099;viernes;24;N-03-99-10;\n"
)

pytestmark = pytest.mark.usefixtures("mocked_aws")


@pytest.fixture
def bucket(write_env) -> Any:  # type: ignore[no-untyped-def]
    write_env(ENV)
    client = boto3.client("s3", region_name=REGION)
    client.create_bucket(Bucket=BUCKET)
    return client


def _keys(client: Any) -> list[str]:
    return [item["Key"] for item in client.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def _data_file(tmp_path: Path, name: str, content: bytes) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    path = tmp_path / "data" / name
    path.write_bytes(content)
    return path


def test_upload_from_data_dir(bucket: Any, tmp_path: Path) -> None:
    _data_file(tmp_path, "mi-campana.csv", FIXTURE.read_bytes())

    result = runner.invoke(app, ["--output", "json", "s3", "upload", "mi-campana.csv"])

    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["bucket"] == BUCKET
    assert data["key"] == "mi-campana.csv"
    head = bucket.head_object(Bucket=BUCKET, Key="mi-campana.csv")
    assert head["ContentType"] == "text/csv"
    assert bucket.get_object(Bucket=BUCKET, Key="mi-campana.csv")["Body"].read() == (
        FIXTURE.read_bytes()
    )


def test_upload_default_key_uses_prefix(write_env, bucket: Any) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_INPUT_PREFIX=entrada\n")

    result = runner.invoke(app, ["s3", "upload", str(FIXTURE)])

    assert result.exit_code == 0, result.stderr
    assert _keys(bucket) == ["entrada/csv-test.csv"]


def test_upload_invalid_csv_uploads_nothing(bucket: Any, tmp_path: Path) -> None:
    _data_file(tmp_path, "malo.csv", INVALID_CSV.encode())

    result = runner.invoke(app, ["s3", "upload", "malo.csv"])

    assert result.exit_code == 1
    assert "no se subió nada" in result.stderr
    assert "horas" in result.stdout
    assert _keys(bucket) == []


def test_upload_invalid_csv_with_no_validate(bucket: Any, tmp_path: Path) -> None:
    _data_file(tmp_path, "malo.csv", INVALID_CSV.encode())

    result = runner.invoke(app, ["s3", "upload", "malo.csv", "--no-validate", "--key", "x.csv"])

    assert result.exit_code == 0, result.stderr
    assert _keys(bucket) == ["x.csv"]


def test_upload_shows_warnings(bucket: Any, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from datetime import datetime

    monkeypatch.setattr(s3_cmd, "colombia_now", lambda: datetime(2099, 12, 25, 15, 0))

    result = runner.invoke(app, ["s3", "upload", str(FIXTURE)])

    assert result.exit_code == 0
    assert "ya pasaron" in result.stderr


def test_upload_missing_file_exits_2(bucket: Any) -> None:
    result = runner.invoke(app, ["s3", "upload", "no-existe.csv"])

    assert result.exit_code == 2
    assert _keys(bucket) == []


def test_ls_newest_first_and_limit(bucket: Any) -> None:
    for name in ("a.csv", "b.csv", "c.csv"):
        bucket.put_object(Bucket=BUCKET, Key=name, Body=b"x")

    result = runner.invoke(app, ["--output", "json", "s3", "ls", "--limit", "2"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    assert set(data[0]) == {"key", "tamano_bytes", "ultima_modificacion"}
    assert "más recientes" in result.stderr


def test_get_prints_to_stdout_or_writes_file(bucket: Any, tmp_path: Path) -> None:
    bucket.put_object(Bucket=BUCKET, Key="a.csv", Body="app_id;canal\nñ\n".encode())

    printed = runner.invoke(app, ["s3", "get", "a.csv"])
    saved = runner.invoke(app, ["s3", "get", "a.csv", "-o", str(tmp_path / "out" / "a.csv")])

    assert printed.exit_code == 0
    assert printed.stdout == "app_id;canal\nñ\n"
    assert saved.exit_code == 0
    assert (tmp_path / "out" / "a.csv").read_text(encoding="utf-8") == "app_id;canal\nñ\n"


def test_get_missing_key_exits_3(bucket: Any) -> None:
    result = runner.invoke(app, ["s3", "get", "no-existe.csv"])

    assert result.exit_code == 3


def test_rm_outside_prefix_is_usage_error(write_env, bucket: Any) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_INPUT_PREFIX=entrada/\n")
    bucket.put_object(Bucket=BUCKET, Key="otro.csv", Body=b"x")

    result = runner.invoke(app, ["s3", "rm", "otro.csv", "--yes"])

    assert result.exit_code == 2
    assert _keys(bucket) == ["otro.csv"]


def test_rm_inside_prefix_with_yes(write_env, bucket: Any) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_INPUT_PREFIX=entrada/\n")
    bucket.put_object(Bucket=BUCKET, Key="entrada/a.csv", Body=b"x")

    result = runner.invoke(app, ["s3", "rm", "entrada/a.csv", "--yes"])

    assert result.exit_code == 0, result.stderr
    assert _keys(bucket) == []


def test_rm_asks_and_no_cancels(bucket: Any) -> None:
    bucket.put_object(Bucket=BUCKET, Key="a.csv", Body=b"x")

    result = runner.invoke(app, ["s3", "rm", "a.csv"], input="n\n")

    assert result.exit_code == 0
    assert "cancelada" in result.stderr
    assert _keys(bucket) == ["a.csv"]


def test_rm_missing_key_exits_3(bucket: Any) -> None:
    result = runner.invoke(app, ["s3", "rm", "no-existe.csv", "--yes"])

    assert result.exit_code == 3


@pytest.mark.parametrize(
    "args", [["upload", str(FIXTURE)], ["rm", "a.csv", "--yes"]], ids=["upload", "rm"]
)
def test_writes_blocked_in_prod(write_env, bucket: Any, args: list[str]) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_ENV=prod\n")
    bucket.put_object(Bucket=BUCKET, Key="a.csv", Body=b"x")

    result = runner.invoke(app, ["s3", *args])

    assert result.exit_code == 2
    assert "prod" in result.stderr
    assert _keys(bucket) == ["a.csv"]


def test_reads_allowed_in_prod(write_env, bucket: Any) -> None:  # type: ignore[no-untyped-def]
    write_env(ENV + "CAMPAIGNS_ENV=prod\n")

    assert runner.invoke(app, ["s3", "ls"]).exit_code == 0


def test_bucket_is_required(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(f"AWS_REGION={REGION}\n")

    result = runner.invoke(app, ["s3", "ls"])

    assert result.exit_code == 2
    assert "CAMPAIGNS_INPUT_BUCKET" in result.stderr


def test_upload_without_argument_uses_the_only_csv(bucket: Any, tmp_path: Path) -> None:
    _data_file(tmp_path, "mi-campana.csv", FIXTURE.read_bytes())

    result = runner.invoke(app, ["s3", "upload"])

    assert result.exit_code == 0, result.stderr
    assert "Archivo: data/mi-campana.csv" in result.stderr
    assert _keys(bucket) == ["mi-campana.csv"]


def test_upload_without_argument_and_several_csv_uploads_nothing(
    bucket: Any, tmp_path: Path
) -> None:
    _data_file(tmp_path, "a.csv", FIXTURE.read_bytes())
    _data_file(tmp_path, "b.csv", FIXTURE.read_bytes())

    result = runner.invoke(app, ["s3", "upload"])

    assert result.exit_code == 2
    assert "a.csv" in result.stderr and "b.csv" in result.stderr
    assert _keys(bucket) == []

    explicit = runner.invoke(app, ["s3", "upload", "b.csv"])
    assert explicit.exit_code == 0, explicit.stderr
    assert _keys(bucket) == ["b.csv"]


@pytest.mark.parametrize("setup", ["sin-carpeta", "vacia", "sin-csv"])
def test_upload_without_argument_and_no_csv_exits_2(
    bucket: Any, tmp_path: Path, setup: str
) -> None:
    if setup != "sin-carpeta":
        (tmp_path / "data").mkdir()
    if setup == "sin-csv":
        (tmp_path / "data" / "notas.txt").write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["s3", "upload"])

    assert result.exit_code == 2
    assert "templates/plantilla.csv" in result.stderr
    assert _keys(bucket) == []


def test_upload_without_argument_still_validates(bucket: Any, tmp_path: Path) -> None:
    _data_file(tmp_path, "malo.csv", INVALID_CSV.encode())

    result = runner.invoke(app, ["s3", "upload"])

    assert result.exit_code == 1
    assert _keys(bucket) == []
