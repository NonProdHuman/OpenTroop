"""Schemas for the fixed report catalog and rendered report data (#147).

Reports are fixed server-side definitions, not an ad-hoc builder: the catalog
advertises each report's typed parameters and whether the caller may run it, and
the data endpoint returns column metadata plus already-projected (and, for the
roster, medically redacted) rows for the web table. CSV is streamed separately
and shares the same columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Row values are report-defined scalars (strings, numbers, booleans, or null).
ReportValue = str | int | float | bool | None


class ReportParamOption(BaseModel):
    """One selectable value for an ``enum`` parameter."""

    value: str
    label: str


class ReportParamSchema(BaseModel):
    """A single typed parameter a report accepts, for rendering a form control."""

    name: str
    type: Literal["enum", "int", "group"]
    label: str
    default: ReportValue = None
    # Present for ``enum`` params; ``group`` params are populated from the tenant's
    # groups by the client, so no static options are shipped here.
    options: list[ReportParamOption] | None = None


class ReportColumnSchema(BaseModel):
    """One column of a rendered report: a stable key plus its display label."""

    key: str
    label: str


class ReportCatalogEntry(BaseModel):
    """A report as advertised by ``GET /reports``."""

    key: str
    title: str
    description: str
    params: list[ReportParamSchema]
    # Whether the caller holds every permission this report needs beyond
    # ``report:read`` (the web catalog hides the ones that are False).
    runnable: bool


class ReportData(BaseModel):
    """A rendered report's columns and rows for the web table (``format=json``)."""

    key: str
    title: str
    generated_at: datetime
    columns: list[ReportColumnSchema]
    rows: list[dict[str, ReportValue]]
