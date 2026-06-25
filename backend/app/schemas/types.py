"""Shared Pydantic field types."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def _ensure_utc(value: datetime) -> datetime:
    """Normalize any datetime to a timezone-aware UTC instant.

    The platform stores and exchanges all timestamps as UTC ISO-8601. Aware
    inputs (e.g. ``...Z`` or ``...+05:00`` from the API) are converted to UTC;
    naive inputs are assumed to already be UTC and stamped accordingly (this
    also normalizes values read back from SQLite, which drops tzinfo).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


# A datetime that is always coerced to timezone-aware UTC, both when parsed from
# a request body and when serialized from an ORM attribute on a read model.
UtcDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]
