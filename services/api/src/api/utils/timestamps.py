"""Timestamp utilities for truncating to time periods (UTC with timezone)."""

from datetime import datetime, timedelta, timezone


def truncate_to_hour(ts: int) -> datetime:
    """Truncate unix timestamp to start of hour (floor). Returns timezone-aware UTC."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def truncate_to_day(ts: int) -> datetime:
    """Truncate unix timestamp to start of day (floor). Returns timezone-aware UTC."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def truncate_to_week(ts: int) -> datetime:
    """Truncate unix timestamp to start of week (Monday, floor). Returns timezone-aware UTC."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    # weekday() returns 0 for Monday
    days_since_monday = dt.weekday()
    monday = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - timedelta(days=days_since_monday)


def truncate_to_month(ts: int) -> datetime:
    """Truncate unix timestamp to start of month (floor). Returns timezone-aware UTC."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def compute_all_truncations(ts: int) -> dict[str, datetime]:
    """Compute all truncated timestamps from a unix timestamp."""
    return {
        "timestamp_hour": truncate_to_hour(ts),
        "timestamp_day": truncate_to_day(ts),
        "timestamp_week": truncate_to_week(ts),
        "timestamp_month": truncate_to_month(ts),
    }
