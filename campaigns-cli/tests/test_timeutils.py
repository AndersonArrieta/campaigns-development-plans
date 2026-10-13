from datetime import datetime, timedelta

import pytest

from campaigns_cli.errors import UsageError
from campaigns_cli.timeutils import hour_floor, parse_datetime, parse_since, to_dynamo


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("15m", timedelta(minutes=15)),
        ("2h", timedelta(hours=2)),
        ("1D", timedelta(days=1)),
    ],
)
def test_parse_since(value: str, expected: timedelta) -> None:
    assert parse_since(value) == expected


@pytest.mark.parametrize("value", ["", "2", "h", "2w", "-1h"])
def test_parse_since_invalid(value: str) -> None:
    with pytest.raises(UsageError):
        parse_since(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-13", datetime(2026, 10, 13)),
        ("2026-10-13 10", datetime(2026, 10, 13, 10)),
        ("2026-10-13 10:30", datetime(2026, 10, 13, 10, 30)),
        ("2026-10-13 10:30:15", datetime(2026, 10, 13, 10, 30, 15)),
        ("2026-10-13T10:30:15", datetime(2026, 10, 13, 10, 30, 15)),
    ],
)
def test_parse_datetime(value: str, expected: datetime) -> None:
    assert parse_datetime(value) == expected


def test_parse_datetime_invalid() -> None:
    with pytest.raises(UsageError, match="13/10/2026"):
        parse_datetime("13/10/2026")


def test_dynamo_format_and_hour_floor() -> None:
    value = datetime(2026, 10, 13, 10, 45, 12, 999)

    assert to_dynamo(hour_floor(value)) == "2026-10-13 10:00:00"
