"""Async TWH import worker (GH-240).

The importer never runs inside its HTTP request anymore: ``POST /import/twh``
persists the payload + an ``ImportJob`` and returns 202, and this module drains
the queue — from the in-process lifespan loop (``IMPORT_LOOP_ENABLED``), the
``drain-import-jobs`` CLI, or a Cloud Tasks push to the worker endpoint.

Design choices:

- **Chunked commits per stage.** The importer commits at each stage boundary
  (patrols → people → … → advancement), so ``stage`` + running counts on the job
  are real progress a poller can watch, and a mid-import failure leaves a
  reportable state rather than minutes of rolled-back work. Partial data left by a
  failure is caught on the next attempt by the router's duplicate pre-check (409 →
  reset the tenant), not silently re-imported.
- **Claiming is atomic** — ``UPDATE … WHERE status='queued'`` — so at-least-once
  delivery (Cloud Tasks retries, two loop instances) processes a job at most once.
- **Duplicate re-imports fail fast and clean.** The router pre-checks for existing
  ``source_system='twh'`` rows (409); if one still races through, the importer's
  ``IntegrityError`` is caught here and turned into a FAILED job with actionable
  guidance instead of a raw 500 after minutes of work.
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tenant_context import tenant_scope, unscoped
from app.importers.twh import TwhImporter, TwhImportResult, resolve_source_tz
from app.models.enums import ImportJobStatus
from app.models.import_job import ImportJob

logger = logging.getLogger(__name__)

_SUMMARY_FIELDS = (
    "patrols",
    "members",
    "relationships",
    "positions",
    "position_assignments",
    "locations",
    "event_types",
    "events",
    "participants",
    "rank_progress",
    "requirement_completions",
    "merit_badges",
    "skipped",
)


def summarize(result: TwhImportResult) -> dict[str, int]:
    """Per-entity counts (no warnings) — the shape stored in ``summary``/``progress``."""
    return {field: getattr(result, field) for field in _SUMMARY_FIELDS}


_DUPLICATE_DETAIL = (
    "This tenant already contains imported TroopWebHost data — re-importing is additive "
    "and would create duplicates. Reset the tenant (uv run reset-tenant) before re-importing."
)


def process_import_job(job_id: uuid.UUID) -> bool:
    """Claim and run one queued import job. Returns True if this call ran it.

    Idempotent and safe under concurrent/duplicate delivery: only the caller that
    flips ``queued → running`` proceeds; everyone else returns False immediately.
    """
    with SessionLocal() as db, unscoped():
        job = db.get(ImportJob, job_id)
        if job is None:
            logger.warning("Import job %s not found", job_id.hex)
            return False
        tenant_id = job.tenant_id

    with SessionLocal() as db, tenant_scope(tenant_id):
        claimed = cast(
            CursorResult[Any],
            db.execute(
                update(ImportJob)
                .where(ImportJob.id == job_id, ImportJob.status == ImportJobStatus.QUEUED)
                .values(status=ImportJobStatus.RUNNING, started_at=datetime.now(UTC))
            ),
        )
        db.commit()
        if claimed.rowcount == 0:
            return False  # already claimed or terminal

    _run_claimed_job(job_id, tenant_id)
    return True


def _run_claimed_job(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    with SessionLocal() as db, tenant_scope(tenant_id):
        job = db.get(ImportJob, job_id)
        assert job is not None  # noqa: S101 — we just claimed it in this tenant scope
        try:
            xml = gzip.decompress(job.payload)
            root = DefusedET.fromstring(xml)
            source_tz = resolve_source_tz(job.source_timezone)
        except (OSError, ET.ParseError, DefusedXmlException, ValueError) as exc:
            _fail(db, job, f"Could not read the stored import payload: {exc}")
            return

        def on_stage(stage: str, res: TwhImportResult) -> None:
            # Chunked commit per stage: persist this stage's rows together with live
            # progress, so a poller sees real advancement and a failure is reportable.
            job.stage = stage
            job.progress = summarize(res)
            db.add(job)
            db.commit()

        importer = TwhImporter(db, tenant_id, source_tz=source_tz)
        try:
            result = importer.run(root, on_progress=on_stage)
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info("Import job %s hit a duplicate-key conflict", job_id.hex)
            _fail(db, job, _DUPLICATE_DETAIL)
            return
        except Exception as exc:  # noqa: BLE001 — any importer error must land as FAILED, not orphan the job
            db.rollback()
            logger.warning("Import job %s crashed", job_id.hex, exc_info=True)
            _fail(db, job, f"Import failed: {exc}")
            return

        job.status = ImportJobStatus.SUCCEEDED
        job.stage = None
        job.summary = summarize(result)
        job.progress = summarize(result)
        job.warnings = result.warnings
        job.finished_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        logger.info("Import job %s succeeded: %s", job_id.hex, job.summary)


def _fail(db: Session, job: ImportJob, error: str) -> None:
    job.status = ImportJobStatus.FAILED
    job.error = error
    job.finished_at = datetime.now(UTC)
    db.add(job)
    db.commit()


def _queued_job_ids() -> list[uuid.UUID]:
    with SessionLocal() as db, unscoped():
        return list(
            db.scalars(
                select(ImportJob.id)
                .where(ImportJob.status == ImportJobStatus.QUEUED, ImportJob.is_deleted.is_(False))
                .order_by(ImportJob.created_at)
            ).all()
        )


def run_import_pass() -> dict[str, int]:
    """Drain every queued import job once. Returns counters. Used by the loop + CLI."""
    ran = 0
    ids = _queued_job_ids()
    for job_id in ids:
        try:
            if process_import_job(job_id):
                ran += 1
        except Exception:  # noqa: BLE001 — one job's failure must not stall the rest
            logger.warning("Import pass failed for job %s", job_id.hex, exc_info=True)
    return {"queued": len(ids), "ran": ran}


async def import_loop() -> None:
    """In-process driver: drain queued import jobs forever until cancelled (lifespan)."""
    from app.core.config import settings

    logger.info("Import loop started (tick every %ss)", settings.import_tick_seconds)
    while True:
        try:
            stats = await asyncio.to_thread(run_import_pass)
            if stats["ran"]:
                logger.info("Import pass: %s", stats)
        except Exception:  # noqa: BLE001 — the loop must survive anything
            logger.warning("Import pass crashed; continuing", exc_info=True)
        await asyncio.sleep(settings.import_tick_seconds)
