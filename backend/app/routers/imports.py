"""Import endpoints — currently supports TroopWebHost XML full-data exports."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from app.core.deps import DbDep, TenantDep, require
from app.importers.twh import TwhImporter, resolve_source_tz
from app.models.enums import Permission
from app.schemas.imports import TwhImportRead

router = APIRouter(prefix="/import", tags=["import"])


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
    Event, and EventParticipant records for the current tenant.  The import is additive;
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        content = file.file.read()
        filename = file.filename.lower() if file.filename else ""
        if filename.endswith(".zip"):
            import io
            import zipfile

            with zipfile.ZipFile(io.BytesIO(content)) as z:
                xml_files = [name for name in z.namelist() if name.lower().endswith(".xml")]
                if not xml_files:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="No XML file found inside ZIP archive.",
                    )
                content = z.read(xml_files[0])
        elif filename.endswith(".gz") or content.startswith(b"\x1f\x8b"):
            import gzip

            try:
                content = gzip.decompress(content)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid GZIP compression: {exc}",
                ) from exc
        root = ET.fromstring(content)  # noqa: S314 — admin-supplied file upload
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        skipped=result.skipped,
        warnings=result.warnings,
    )
