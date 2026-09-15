"""UTC helpers.

``datetime.utcnow()`` is deprecated from Python 3.12 onwards and returns a
naive value, which is why mixing it with timezone-aware timestamps produced
inconsistent SLA maths. These helpers keep one convention: naive UTC, matching
the ``TIMESTAMP`` columns the models have always used.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (column-friendly)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime | None) -> datetime | None:
    """Normalise any datetime (naive or aware) to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
