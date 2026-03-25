"""UTC time helpers for consistent timestamp generation."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""

    return datetime.now(tz=UTC)


def format_utc_filename_timestamp(timestamp: datetime) -> str:
    """Format UTC datetime as compact sortable filename component."""

    return timestamp.strftime("%Y%m%dT%H%M%SZ")
