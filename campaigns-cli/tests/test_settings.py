from pathlib import Path

import pytest

from campaigns_cli.settings import (
    Env,
    MissingSettingError,
    OutputFormat,
    SettingsError,
    is_sensitive,
    load_settings,
    mask,
    setting_sources,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FULL_ENV = """
CAMPAIGNS_ENV=qa
AWS_PROFILE=finaipro-qa
AWS_REGION=us-east-2
CAMPAIGNS_INPUT_BUCKET=bucket-qa
CAMPAIGNS_INPUT_PREFIX=input/
CAMPAIGNS_TABLE_NAME=campaigns-qa
CAMPAIGNS_TABLE_CAMPAIGN_INDEX=campaign_id-index
INGESTER_LAMBDA_NAME=ingester-qa
SCHEDULER_LAMBDA_NAME=scheduler-qa
CAMPAIGNS_LOG_GROUPS=a, b,,c
CLI_OUTPUT=json
CLI_WAIT_TIMEOUT_SECONDS=60
CLI_POLL_INTERVAL_SECONDS=2
CLI_TEST_APP_ID=app-test
"""


def test_loads_all_values_from_env_file(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env(FULL_ENV)

    settings = load_settings()

    assert settings.campaigns_env is Env.QA
    assert settings.aws_profile == "finaipro-qa"
    assert settings.aws_region == "us-east-2"
    assert settings.campaigns_input_bucket == "bucket-qa"
    assert settings.campaigns_input_prefix == "input/"
    assert settings.campaigns_table_name == "campaigns-qa"
    assert settings.campaigns_table_campaign_index == "campaign_id-index"
    assert settings.ingester_lambda_name == "ingester-qa"
    assert settings.scheduler_lambda_name == "scheduler-qa"
    assert settings.campaigns_log_groups == ["a", "b", "c"]
    assert settings.cli_output is OutputFormat.JSON
    assert settings.cli_wait_timeout_seconds == 60
    assert settings.cli_poll_interval_seconds == 2
    assert settings.cli_test_app_id == "app-test"


def test_defaults_without_env_file() -> None:
    settings = load_settings()

    assert settings.campaigns_env is Env.DEV
    assert settings.campaigns_input_bucket is None
    assert settings.campaigns_log_groups == []
    assert settings.cli_output is OutputFormat.TABLE


def test_env_example_is_loadable() -> None:
    settings = load_settings(PROJECT_ROOT / ".env.example")

    assert settings.campaigns_env is Env.DEV
    assert settings.aws_profile is None
    assert settings.campaigns_table_name is None
    assert settings.campaigns_log_groups == []
    assert settings.cli_test_app_id == "others-test"


def test_process_env_overrides_env_file(write_env, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_TABLE_NAME=desde-archivo\n")
    monkeypatch.setenv("CAMPAIGNS_TABLE_NAME", "desde-proceso")

    settings = load_settings()

    assert settings.campaigns_table_name == "desde-proceso"


def test_custom_env_file(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_ENV=dev\n")
    qa_file = write_env("CAMPAIGNS_ENV=qa\n", name=".env.qa")

    assert load_settings(qa_file).campaigns_env is Env.QA


def test_missing_custom_env_file(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="No existe"):
        load_settings(tmp_path / "inexistente.env")


def test_invalid_env_value_has_clear_message(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_ENV=staging\n")

    with pytest.raises(SettingsError, match="CAMPAIGNS_ENV") as exc_info:
        load_settings()

    assert "staging" in str(exc_info.value)


def test_require_reports_missing_variables(write_env) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_TABLE_NAME=\nCAMPAIGNS_INPUT_BUCKET=bucket\n")
    settings = load_settings()

    settings.require("campaigns_input_bucket")
    with pytest.raises(MissingSettingError) as exc_info:
        settings.require("campaigns_input_bucket", "campaigns_table_name", "campaigns_log_groups")

    assert exc_info.value.variables == ["CAMPAIGNS_TABLE_NAME", "CAMPAIGNS_LOG_GROUPS"]


def test_setting_sources(write_env, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    write_env("CAMPAIGNS_TABLE_NAME=tabla\n")
    monkeypatch.setenv("AWS_REGION", "us-west-2")

    sources = setting_sources()

    assert sources["campaigns_table_name"] == ".env"
    assert sources["aws_region"] == "env"
    assert sources["campaigns_env"] == "default"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AWS_SECRET_ACCESS_KEY", True),
        ("api_token", True),
        ("DB_PASSWORD", True),
        ("CAMPAIGNS_TABLE_NAME", False),
    ],
)
def test_is_sensitive(name: str, expected: bool) -> None:
    assert is_sensitive(name) is expected


def test_mask_hides_value() -> None:
    assert mask("abc") == "****"
    assert mask("supersecreto") == "su****to"
