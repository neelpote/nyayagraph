from datetime import datetime, timezone


def utc_now() -> datetime:
    """UTC as a naive datetime for the MVP's existing database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
