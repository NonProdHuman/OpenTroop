"""Import endpoints — currently supports TroopWebHost XML full-data exports.

Upload handling is deliberately defensive (GH-175 Finding 2): the raw upload,
gzip stream, and zip entry are all read through a byte-capped chunked reader so
a crafted archive bomb cannot expand into gigabytes of process memory, and XML
is parsed with ``defusedxml`` so entity/DTD attacks are rejected. Size-limit
rejections return 413; malformed or hostile content returns 422. Limits live in
``Settings`` (``twh_import_max_*``) so self-hosted deployments can tune them.
"""

from __future__ import annotations

import gzip
import io
import uuid
import zipfile
import zlib
from typing import Annotated, Protocol
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentMemberDep, DbDep, TenantDep, require
from app.core.import_jobs import process_import_job
from app.core.import_queue import enqueue_import_job
from app.core.import_worker_auth import verify_worker_oidc
from app.importers.twh import resolve_source_tz
from app.models.enums import ImportJobStatus, Permission
from app.models.import_job import ImportJob
from app.models.member import Member
from app.schemas.imports import ImportJobRead

router = APIRouter(prefix="/import", tags=["import"])

_CHUNK_SIZE = 64 * 1024


class _Readable(Protocol):
    def read(self, size: int, /) -> bytes:
        """Read up to *size* bytes."""


def _read_capped(stream: _Readable, limit: int, detail: str) -> bytes:
    """Read *stream* to EOF, aborting with 413 once more than *limit* bytes appear.

    Chunked so neither a huge raw upload nor an unbounded decompression stream
    (gzip/zip bomb) is ever materialized past the cap. Never trusts declared
    sizes (Content-Length, ``ZipInfo.file_size``) — only bytes actually read.
    """
    buf = bytearray()
    while True:
        chunk = stream.read(_CHUNK_SIZE)
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)


def _extract_xml_bytes(upload: UploadFile) -> bytes:
    """Return the XML payload from a raw/.zip/.gz upload, enforcing size caps."""
    content = _read_capped(
        upload.file,
        settings.twh_import_max_upload_bytes,
        "Upload exceeds the maximum allowed size",
    )
    filename = upload.filename.lower() if upload.filename else ""
    decompressed_detail = "Decompressed upload exceeds the maximum allowed size"

    if filename.endswith(".zip"):
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid ZIP archive: {exc}",
            ) from exc
        with archive as z:
            names = z.namelist()
            if len(names) > settings.twh_import_max_zip_entries:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="ZIP archive contains too many entries",
                )
            xml_files = [name for name in names if name.lower().endswith(".xml")]
            if not xml_files:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="No XML file found inside ZIP archive.",
                )
            with z.open(xml_files[0]) as entry:
                return _read_capped(
                    entry, settings.twh_import_max_decompressed_bytes, decompressed_detail
                )

    if filename.endswith(".gz") or content.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz_stream:
                return _read_capped(
                    gz_stream, settings.twh_import_max_decompressed_bytes, decompressed_detail
                )
        except HTTPException:
            raise
        except (OSError, EOFError, zlib.error) as exc:  # BadGzipFile is an OSError
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid GZIP compression: {exc}",
            ) from exc

    return content


@router.post(
    "/twh",
    response_model=ImportJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a TroopWebHost XML full-data export for import",
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def import_twh(
    file: UploadFile,
    tenant_id: TenantDep,
    db: DbDep,
    member: CurrentMemberDep,
    timezone: str = Form(
        "UTC",
        description=(
            "IANA timezone the export's local times are in (e.g. America/New_York). "
            "Times are converted to UTC on import."
        ),
    ),
) -> ImportJob:
    """Validate and **queue** a TroopWebHost XML export; the import runs in the background.

    A real full-troop export takes minutes to import against a remote database — far
    longer than a gateway request timeout (GH-240). So this endpoint validates the
    upload synchronously (size caps, XML well-formedness, timezone), stores the
    compressed payload, creates an :class:`ImportJob`, and returns **202** with the job.
    Poll ``GET /import/jobs/{id}`` for progress and the final summary + warnings.

    Rejects fast (409) when the tenant already contains imported TWH data (re-import
    is additive and would duplicate) or already has an import running — so a retry
    never stacks a second concurrent or duplicate import.
    """
    try:
        resolve_source_tz(timezone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    content = _extract_xml_bytes(file)
    try:
        DefusedET.fromstring(content)  # well-formedness + entity-attack check only
    except (ET.ParseError, DefusedXmlException) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid XML: {exc}",
        ) from exc

    _reject_if_already_imported(db)
    _reject_if_import_active(db)

    job = ImportJob(
        status=ImportJobStatus.QUEUED,
        source_timezone=timezone,
        original_filename=file.filename,
        requested_by_id=member.id,
        payload=gzip.compress(content),
        payload_bytes=len(content),
    )
    db.add(job)
    try:
        db.commit()
    except Exception as exc:  # the partial unique index is the backstop for the active-job race
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An import is already in progress for this tenant.",
        ) from exc
    db.refresh(job)

    enqueue_import_job(job.id)
    return job


def _reject_if_already_imported(db: Session) -> None:
    if db.scalar(select(Member.id).where(Member.source_system == "twh").limit(1)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This tenant already contains imported TroopWebHost data. Re-importing is "
                "additive and would create duplicates — reset the tenant before re-importing."
            ),
        )


def _reject_if_import_active(db: Session) -> None:
    active = db.scalar(
        select(ImportJob.id).where(
            ImportJob.status.in_([ImportJobStatus.QUEUED, ImportJobStatus.RUNNING])
        )
    )
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An import is already in progress for this tenant.",
        )


@router.get(
    "/jobs",
    response_model=list[ImportJobRead],
    summary="List import jobs for the current tenant (newest first)",
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def list_import_jobs(db: DbDep) -> list[ImportJob]:
    return list(db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc())).all())


@router.get(
    "/jobs/{job_id}",
    response_model=ImportJobRead,
    summary="Get one import job (poll for progress and the final summary)",
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def get_import_job(job_id: uuid.UUID, db: DbDep) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return job


@router.post(
    "/jobs/execute",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Internal: run a queued import job (Cloud Tasks worker endpoint)",
    include_in_schema=False,
)
def execute_import_job(
    request: Request,
    payload: Annotated[dict[str, str], Body()],
) -> dict[str, bool]:
    """Cloud Tasks push target — verifies the OIDC token, then runs the job.

    Not tenant-scoped and not behind ``require()``: authentication is the Google OIDC
    token minted by Cloud Tasks (see ``import_worker_auth``). Inert (403) under the
    default ``inprocess`` backend, where nothing pushes here.
    """
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    verify_worker_oidc(token)
    job_id = uuid.UUID(payload["job_id"])
    ran = process_import_job(job_id)
    return {"ran": ran}
