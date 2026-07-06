"""Consent ledger API (#223): record, list, and revoke consents.

One ledger, many scopes — ToS acceptance, COPPA parental consent, media release,
SMS opt-in. Recording/revoking is gated on ``member:write`` and viewing on
``member:read``; the later phases (age-tier gating, parent-initiated child
consent, claim-time disclosures) build on this substrate.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import (
    CurrentUserDep,
    DbDep,
    TenantDep,
    get_or_404,
    require,
    require_tenant_fk,
)
from app.models.consent import ConsentRecord
from app.models.enums import ConsentScope, Permission
from app.models.member import Member
from app.schemas.consent import ConsentRecordCreate, ConsentRecordRead

router = APIRouter(prefix="/consents", tags=["consents"])


@router.get(
    "",
    response_model=list[ConsentRecordRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_consents(
    tenant_id: TenantDep,
    db: DbDep,
    subject_member_id: Annotated[uuid.UUID | None, Query()] = None,
    scope: Annotated[ConsentScope | None, Query()] = None,
) -> Sequence[ConsentRecord]:
    q = select(ConsentRecord).where(ConsentRecord.is_deleted.is_(False))
    if subject_member_id is not None:
        q = q.where(ConsentRecord.subject_member_id == subject_member_id)
    if scope is not None:
        q = q.where(ConsentRecord.scope == scope)
    return db.scalars(q.order_by(ConsentRecord.granted_at.desc())).all()


@router.post(
    "",
    response_model=ConsentRecordRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def record_consent(
    body: ConsentRecordCreate, user: CurrentUserDep, tenant_id: TenantDep, db: DbDep
) -> ConsentRecord:
    require_tenant_fk(db, Member, body.subject_member_id, "subject_member_id")
    if body.consented_by_member_id is not None:
        require_tenant_fk(db, Member, body.consented_by_member_id, "consented_by_member_id")
    record = ConsentRecord(
        subject_member_id=body.subject_member_id,
        consented_by_member_id=body.consented_by_member_id,
        consented_by_user_id=user.id,
        scope=body.scope,
        method=body.method,
        granted_at=body.granted_at or datetime.now(UTC),
        policy_version=body.policy_version,
        notes=body.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post(
    "/{consent_id}/revoke",
    response_model=ConsentRecordRead,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def revoke_consent(consent_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> ConsentRecord:
    record = get_or_404(db, ConsentRecord, consent_id, "Consent record not found")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)
    return record
