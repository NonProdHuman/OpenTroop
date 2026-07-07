"""Report catalog + rendering endpoints (#147).

``GET /reports`` advertises the fixed report catalog with a per-report
``runnable`` flag for the caller; ``GET /reports/{key}`` renders one report as
JSON rows (for the web table) or a streamed CSV attachment. Everything is gated
``report:read``; a report may require extra permissions (the medical report needs
``member:read_medical``) which are enforced here, 403 on absence.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.deps import DbDep, MemberContextDep, require
from app.core.reports import REPORTS, ReportDefinition
from app.models.enums import Permission
from app.schemas.report import ReportCatalogEntry, ReportData, ReportValue

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require(Permission.REPORT_READ))],
)


def _get_definition(key: str) -> ReportDefinition:
    definition = REPORTS.get(key)
    if definition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    return definition


@router.get("", response_model=list[ReportCatalogEntry])
def list_reports(ctx: MemberContextDep) -> list[ReportCatalogEntry]:
    """The report catalog with a ``runnable`` flag per report for this caller."""
    _caller, permissions = ctx
    return [definition.catalog_entry(permissions) for definition in REPORTS.values()]


def _csv_stream(
    columns: list[str], header: list[str], rows: list[dict[str, ReportValue]]
) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(header)
    yield flush()
    for row in rows:
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in columns])
        yield flush()


@router.get("/{key}", response_model=ReportData)
def run_report(
    key: str,
    request: Request,
    ctx: MemberContextDep,
    db: DbDep,
    format: Literal["json", "csv"] = Query("json"),
) -> ReportData | StreamingResponse:
    """Render report ``key``. ``format=json`` returns rows for the web table;
    ``format=csv`` streams a CSV attachment. Report parameters are read from the
    query string per the report's declared parameter schema."""
    caller, permissions = ctx
    definition = _get_definition(key)
    if not definition.runnable_by(permissions):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to run this report",
        )

    parsed = definition.parse_params(request.query_params)
    rows = definition.builder(parsed, caller, permissions, db)

    if format == "csv":
        column_keys = [c.key for c in definition.columns]
        header = [c.label for c in definition.columns]
        filename = f"{definition.key}-report.csv"
        return StreamingResponse(
            _csv_stream(column_keys, header, rows),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return ReportData(
        key=definition.key,
        title=definition.title,
        generated_at=datetime.now(UTC),
        columns=list(definition.columns),
        rows=rows,
    )
