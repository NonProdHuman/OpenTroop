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
import zipfile
import zlib
from typing import Protocol
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import DbDep, TenantDep, require
from app.importers.twh import TwhImporter, resolve_source_tz
from app.models.enums import Permission
from app.schemas.imports import TwhImportRead

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
    response_model=TwhImportRead,
    summary="Import a TroopWebHost XML full-data export",
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def import_twh(
    file: UploadFile,
    tenant_id: TenantDep,
    db: DbDep,
    timezone: str = Form(
        "UTC",
        description=(
            "IANA timezone the export's local times are in (e.g. America/New_York). "
            "Times are converted to UTC on import."
        ),
    ),
) -> TwhImportRead:
    """Upload a TroopWebHost XML export and import its roster and events.

    Creates Patrol, Member, MemberRelationship, Position (with dated
    MemberPositionAssignment terms for leadership history), Location, EventType,
    Event, EventParticipant, and advancement records (MemberRankProgress,
    MemberRequirementCompletion, MemberMeritBadge — requires the global
    advancement catalog to be seeded) for the current tenant.  The import is additive;
    running it twice will attempt to create duplicate records (BSA ID uniqueness
    will raise a 409 on the second run if the same persons are re-imported).

    ``timezone`` is the IANA zone the export's naive datetimes are expressed in;
    they are converted to UTC for storage (defaults to UTC).

    Returns a summary of created and skipped records, plus any warnings for
    rows that could not be mapped (unknown foreign keys, missing required fields).
    """
    try:
        source_tz = resolve_source_tz(timezone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    content = _extract_xml_bytes(file)
    try:
        root = DefusedET.fromstring(content)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid XML: {exc}",
        ) from exc

    result = TwhImporter(db, tenant_id, source_tz=source_tz).run(root)
    db.commit()

    return TwhImportRead(
        patrols=result.patrols,
        members=result.members,
        relationships=result.relationships,
        positions=result.positions,
        position_assignments=result.position_assignments,
        locations=result.locations,
        event_types=result.event_types,
        events=result.events,
        participants=result.participants,
        rank_progress=result.rank_progress,
        requirement_completions=result.requirement_completions,
        merit_badges=result.merit_badges,
        skipped=result.skipped,
        warnings=result.warnings,
    )
