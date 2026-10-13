from collections.abc import Iterator
from pathlib import Path

import pytest

from campaigns_cli.settings import Settings, env_var_name


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Aísla cada prueba del .env real y de las variables del proceso."""
    for field in Settings.model_fields:
        monkeypatch.delenv(env_var_name(field), raising=False)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture
def write_env(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _write(content: str, name: str = ".env") -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _write
