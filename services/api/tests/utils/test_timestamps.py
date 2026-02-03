from datetime import datetime, timezone

from services.api.src.api.utils.timestamps import (
    truncate_to_day,
    truncate_to_hour,
    truncate_to_month,
    truncate_to_week,
)


class TestTruncateToHour:
    def test_truncates_minutes_and_seconds(self):
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = truncate_to_hour(ts)
        expected = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_preserves_exact_hour(self):
        ts = 1699999200  # 2023-11-14 22:00:00 UTC
        result = truncate_to_hour(ts)
        expected = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestTruncateToDay:
    def test_truncates_to_midnight(self):
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = truncate_to_day(ts)
        expected = datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestTruncateToWeek:
    def test_truncates_to_monday(self):
        ts = 1700000725  # 2023-11-14 22:25:25 UTC (Tuesday)
        result = truncate_to_week(ts)
        expected = datetime(2023, 11, 13, 0, 0, 0, tzinfo=timezone.utc)  # Monday
        assert result == expected


class TestTruncateToMonth:
    def test_truncates_to_first_of_month(self):
        ts = 1700000725  # 2023-11-14 22:25:25 UTC
        result = truncate_to_month(ts)
        expected = datetime(2023, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected
