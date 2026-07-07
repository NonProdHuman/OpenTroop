"""Async import job (GH-240).

`POST /import/twh` no longer rides a single HTTP request end-to-end: it validates
+ stores the compressed payload, creates an ``ImportJob`` row, and returns 202. A
worker (in-process loop or Cloud Tasks push, per ``IMPORT_QUEUE_BACKEND``) picks the
job up, runs the importer, and writes the outcome back onto the row. The row is the
durable home for the summary and — critically — the **warnings** that a gateway 504
used to eat (e.g. "advancement catalog not seeded"). See the events importer in
``app/importers/twh.py`` and the driver in ``app/core/import_jobs.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TrackedBase
from app.models.enums import ImportJobStatus
from app.models.types import JsonDict, JsonList


class ImportJob(TrackedBase):
    """One TWH import request, from enqueue through terminal state.

    The compressed source payload lives on the row (``payload`` — the upload zip is
    <1 MB, so a bytea column keeps self-host dependency-free; a GCS handle can
    replace it later if payloads grow). ``progress``/``summary`` are free-form JSON
    so the shape can evolve without a migration. A partial unique index enforces
    **at most one active (queued/running) job per tenant** so a retry can't spawn a
    second concurrent import.
    """

    __tablename__ = "import_jobs"
    __table_args__ = (
        # One active import per tenant (idempotency guard, GH-240 §4).
        Index(
            "uix_import_jobs_one_active_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_import_jobs_tenant_status", "tenant_id", "status"),
    )

    status: Mapped[ImportJobStatus] = mapped_column(
        SAEnum(ImportJobStatus, values_callable=lambda x: [e.value for e in x]),
        default=ImportJobStatus.QUEUED,
        nullable=False,
    )
    # Human-readable current phase (e.g. "members", "participants") for the UI.
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Per-entity running counts, mirrored from the importer result as it advances.
    progress: Mapped[dict[str, Any] | None] = mapped_column(JsonDict, nullable=True)
    # Final per-entity summary (same shape as the old synchronous response).
    summary: Mapped[dict[str, Any] | None] = mapped_column(JsonDict, nullable=True)
    # Non-fatal warnings surfaced by the importer — the durable, visible home a
    # gateway timeout used to destroy.
    warnings: Mapped[list[str] | None] = mapped_column(JsonList, nullable=True)
    # Failure detail when status is FAILED (short, user-facing).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The member who requested the import (audit; nullable if the member is later purged).
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # IANA zone the export's naive datetimes are in — passed through to the importer.
    source_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    # gzip-compressed XML payload the worker decompresses, parses, and imports.
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Uncompressed XML size in bytes (for display; the payload column is compressed).
    payload_bytes: Mapped[int] = mapped_column(nullable=False, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
