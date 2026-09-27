"""Writing dates in tests the way they read in the reference tables."""

from __future__ import annotations

from datetime import datetime


def at(value: str) -> datetime:
    """Return the aware datetime ``value`` spells in ISO 8601, refusing one with no zone."""
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"{value} needs a timezone"
    return parsed
