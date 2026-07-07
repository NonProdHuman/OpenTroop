from __future__ import annotations

import uuid
from datetime import datetime

from app.models.enums import ImportJobStatus
from app.schemas.base import TrackedRead


class ImportJobRead(TrackedRead):
    """An async import job (GH-240) — returned by POST (202) and the poll endpoints."""

    status: ImportJobStatus
    stage: str | None
    progress: dict[str, int] | None
    summary: dict[str, int] | None
    warnings: list[str] | None
    error: str | None
    requested_by_id: uuid.UUID | None
    original_filename: str | None
    source_timezone: str
    payload_bytes: int
    started_at: datetime | None
    finished_at: datetime | None
