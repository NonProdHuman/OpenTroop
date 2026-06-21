import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from uuid6 import uuid7

from app.core.deps import DbDep, TenantDep
from app.models.member import Member
from app.models.relationship import MemberRelationship
from app.schemas.relationship import (
    MemberRelationshipBase,
    MemberRelationshipRead,
    MemberRelationshipUpdate,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])


def _get_or_404(db, rel_id: uuid.UUID, tenant_id: uuid.UUID) -> MemberRelationship:
    rel = db.get(MemberRelationship, rel_id)
    if not rel or rel.tenant_id != tenant_id or rel.is_deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return rel


def _check_member_tenant(db, member_id: uuid.UUID, tenant_id: uuid.UUID, field: str) -> None:
    member = db.get(Member, member_id)
    if not member or member.tenant_id != tenant_id or member.is_deleted:
        raise HTTPException(status_code=422, detail=f"{field} not found in this tenant")


@router.get("/", response_model=list[MemberRelationshipRead])
def list_relationships(
    tenant_id: TenantDep,
    db: DbDep,
    member_id: Annotated[uuid.UUID | None, Query()] = None,
):
    q = select(MemberRelationship).where(
        MemberRelationship.tenant_id == tenant_id,
        MemberRelationship.is_deleted.is_(False),
    )
    if member_id is not None:
        q = q.where(
            or_(
                MemberRelationship.from_member_id == member_id,
                MemberRelationship.to_member_id == member_id,
            )
        )
    return db.scalars(q).all()


@router.post("/", response_model=MemberRelationshipRead, status_code=201)
def create_relationship(body: MemberRelationshipBase, tenant_id: TenantDep, db: DbDep):
    _check_member_tenant(db, body.from_member_id, tenant_id, "from_member_id")
    _check_member_tenant(db, body.to_member_id, tenant_id, "to_member_id")
    rel = MemberRelationship(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/{rel_id}", response_model=MemberRelationshipRead)
def get_relationship(rel_id: uuid.UUID, tenant_id: TenantDep, db: DbDep):
    return _get_or_404(db, rel_id, tenant_id)


@router.patch("/{rel_id}", response_model=MemberRelationshipRead)
def update_relationship(
    rel_id: uuid.UUID, body: MemberRelationshipUpdate, tenant_id: TenantDep, db: DbDep
):
    rel = _get_or_404(db, rel_id, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rel, k, v)
    db.commit()
    db.refresh(rel)
    return rel


@router.delete("/{rel_id}", status_code=204)
def delete_relationship(rel_id: uuid.UUID, tenant_id: TenantDep, db: DbDep):
    rel = _get_or_404(db, rel_id, tenant_id)
    rel.is_deleted = True
    db.commit()
