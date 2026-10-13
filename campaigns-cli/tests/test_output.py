import json
from datetime import datetime
from decimal import Decimal

import pytest

from campaigns_cli.output import render, to_json
from campaigns_cli.settings import Env, OutputFormat


def test_json_output_is_valid(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [
        {"id": "a", "intentos": Decimal("3"), "costo": Decimal("1.5"), "env": Env.DEV},
        {"id": "b", "fecha": datetime(2026, 10, 13, 10, 0)},
    ]

    render(rows, OutputFormat.JSON)

    captured = capsys.readouterr()
    assert json.loads(captured.out) == [
        {"id": "a", "intentos": 3, "costo": 1.5, "env": "dev"},
        {"id": "b", "fecha": "2026-10-13T10:00:00"},
    ]
    assert captured.err == ""


def test_json_keeps_non_ascii() -> None:
    assert "campañas" in to_json({"texto": "campañas"})


def test_table_output_for_rows(capsys: pytest.CaptureFixture[str]) -> None:
    render(
        [{"recurso": "S3 bucket", "estado": "OK"}, {"recurso": "Lambda", "estado": "NO EXISTE"}],
        OutputFormat.TABLE,
        title="Recursos",
    )

    out = capsys.readouterr().out
    assert "Recursos" in out
    assert "S3 bucket" in out
    assert "NO EXISTE" in out


def test_table_output_for_mapping(capsys: pytest.CaptureFixture[str]) -> None:
    render({"cuenta": "123456789012", "activo": True}, OutputFormat.TABLE)

    out = capsys.readouterr().out
    assert "123456789012" in out
    assert "sí" in out


def test_table_escapes_markup(capsys: pytest.CaptureFixture[str]) -> None:
    render([{"mensaje": "[red]no es markup[/red]"}], OutputFormat.TABLE)

    assert "[red]no es markup[/red]" in capsys.readouterr().out


def test_empty_rows_message_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    render([], OutputFormat.TABLE)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Sin resultados" in captured.err


def test_empty_rows_json(capsys: pytest.CaptureFixture[str]) -> None:
    render([], OutputFormat.JSON)

    assert json.loads(capsys.readouterr().out) == []
