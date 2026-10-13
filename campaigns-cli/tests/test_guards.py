import pytest
import typer

from campaigns_cli import guards
from campaigns_cli.errors import UsageError
from campaigns_cli.settings import Env, Settings
from campaigns_cli.state import AppState


def test_ensure_not_prod_blocks_prod() -> None:
    with pytest.raises(UsageError, match="'s3 rm' no está permitido en prod"):
        guards.ensure_not_prod(Settings(campaigns_env=Env.PROD), "s3 rm")


@pytest.mark.parametrize("env", [Env.DEV, Env.QA])
def test_ensure_not_prod_allows_other_envs(env: Env) -> None:
    guards.ensure_not_prod(Settings(campaigns_env=env), "s3 rm")


def test_confirm_with_yes_does_not_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> bool:
        raise AssertionError("no debería preguntar")

    monkeypatch.setattr(typer, "confirm", fail_if_called)

    guards.confirm_destructive(AppState(assume_yes=True), "¿Borrar?")


def test_confirm_rejected_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: False)

    with pytest.raises(typer.Exit) as exc_info:
        guards.confirm_destructive(AppState(), "¿Borrar?")

    assert exc_info.value.exit_code == 0


def test_confirm_accepted_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: True)

    guards.confirm_destructive(AppState(), "¿Borrar?")
