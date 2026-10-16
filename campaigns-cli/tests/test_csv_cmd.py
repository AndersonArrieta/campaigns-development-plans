import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from campaigns_cli.aws import AwsClients
from campaigns_cli.commands import csv_cmd
from campaigns_cli.main import app

runner = CliRunner(env={"COLUMNS": "250"})

FIXTURE = Path(__file__).parent / "fixtures" / "csv-test.csv"
# Viernes 16/10/2026, 09:30 en Colombia.
NOW = datetime(2026, 10, 16, 9, 30)
HEADER = "app_id;canal;usuario;fecha_inicio;fecha_fin;dias;horas;nodo;parametros"

GENERATE = (
    "csv",
    "generate",
    "--users",
    "573232540390,573001112233",
    "--canal",
    "WhatsApp",
    "--fecha",
    "hoy",
    "--hora",
    "10",
    "--nodo",
    "N-03-99-10",
)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csv_cmd, "colombia_now", lambda: NOW)


@pytest.fixture(autouse=True)
def no_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """`csv` no debe crear clientes AWS ni exigir credenciales."""

    def fail(self: AwsClients) -> Any:
        raise AssertionError("csv no debe crear una sesión AWS")

    monkeypatch.setattr(AwsClients, "session", property(fail))


def _json(*args: str) -> tuple[int, Any, str]:
    result = runner.invoke(app, ["--output", "json", *args])
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result.exit_code, data, result.stderr


def test_validate_reference_fixture() -> None:
    result = runner.invoke(app, ["csv", "validate", str(FIXTURE)])

    assert result.exit_code == 0, result.stderr
    assert "sin problemas" in result.stderr


def test_validate_finds_file_in_data_dir(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "mi-campana.csv").write_bytes(FIXTURE.read_bytes())

    code, data, _ = _json("csv", "validate", "mi-campana.csv")

    assert code == 0
    assert data["archivo"] == "data/mi-campana.csv"
    assert data["errores"] == 0


def test_validate_invalid_exits_1_with_json(tmp_path: Path) -> None:
    path = tmp_path / "malo.csv"
    path.write_text(
        HEADER
        + "\nothers-test;WhatsApp;573232540390;16/10/2026;16/10/2026;viernes;24;N-03-99-10;\n",
        encoding="utf-8",
    )

    code, data, stderr = _json("csv", "validate", str(path))

    assert code == 1
    assert data["errores"] == 1
    assert data["problemas"][0] == {
        "fila": 2,
        "columna": "horas",
        "severidad": "ERROR",
        "mensaje": "Horas inválidas '24': enteros entre 0 y 23.",
    }
    assert "1 error(es)" in stderr


def test_validate_missing_file_exits_2() -> None:
    result = runner.invoke(app, ["csv", "validate", "no-existe.csv"])

    assert result.exit_code == 2


def test_generate_defaults_to_data_dir_and_today(tmp_path: Path) -> None:
    code, data, stderr = _json(*GENERATE)

    assert code == 0, stderr
    path = Path(data["archivo"])
    assert path.parent == Path("data")
    assert path.name == "campaign-20261016-093000.csv"
    assert [row["dias"] for row in data["filas"]] == ["viernes", "viernes"]
    assert data["filas"][0]["app_id"] == "others-test"  # CLI_TEST_APP_ID
    assert data["filas"][0]["fecha_inicio"] == "16/10/2026"

    validated = runner.invoke(app, ["csv", "validate", path.name])
    assert validated.exit_code == 0


def test_generate_with_output_and_options(tmp_path: Path) -> None:
    out = tmp_path / "otra" / "c.csv"

    result = runner.invoke(
        app,
        [
            *GENERATE[:9],
            "+1",
            *GENERATE[10:],
            "--fecha-fin",
            "mañana",
            "--app-id",
            "mi-app",
            "--parametros",
            "nombre=Ana",
            "-o",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[1] == (
        "mi-app;WhatsApp;573232540390;16/10/2026;17/10/2026;viernes,sabado;10;N-03-99-10;nombre:Ana"
    )


def test_generate_invalid_values_writes_nothing(tmp_path: Path) -> None:
    args = list(GENERATE)
    args[3] = "3232540390"  # sin indicativo de país

    result = runner.invoke(app, args)

    assert result.exit_code == 2
    assert "no se escribió nada" in result.stderr
    assert not (tmp_path / "data").exists()


def test_generate_warns_past_hour() -> None:
    args = list(GENERATE)
    args[9] = "8"

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "ya pasaron" in result.stdout


def test_generate_bad_hour_offset_exits_2() -> None:
    args = list(GENERATE)
    args[9] = "+20"

    result = runner.invoke(app, args)

    assert result.exit_code == 2
