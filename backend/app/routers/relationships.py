import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.core.deps import DbDep, TenantDep, get_or_404, require_tenant_fk
from app.models.member import Member
from app.models.relationship import MemberRelationship
from app.schemas.relationship import (
    MemberRelationshipBase,
    MemberRelationshipRead,
    MemberRelationshipUpdate,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.get("/", response_model=list[MemberRelationshipRead])
def list_relationships(
    tenant_id: TenantDep,
    db: DbDep,
    member_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Sequence[MemberRelationship]:
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
def create_relationship(
    body: MemberRelationshipBase, tenant_id: TenantDep, db: DbDep
) -> MemberRelationship:
    require_tenant_fk(db, Member, body.from_member_id, tenant_id, "from_member_id")
    require_tenant_fk(db, Member, body.to_member_id, tenant_id, "to_member_id")
    rel = MemberRelationship(tenant_id=tenant_id, **body.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/{rel_id}", response_model=MemberRelationshipRead)
def get_relationship(rel_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> MemberRelationship:
    return get_or_404(db, MemberRelationship, rel_id, tenant_id, "Relationship not found")


@router.patch("/{rel_id}", response_model=MemberRelationshipRead)
def update_relationship(
    rel_id: uuid.UUID, body: MemberRelationshipUpdate, tenant_id: TenantDep, db: DbDep
) -> MemberRelationship:
    rel = get_or_404(db, MemberRelationship, rel_id, tenant_id, "Relationship not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rel, k, v)
    db.commit()
    db.refresh(rel)
    return rel


@router.delete("/{rel_id}", status_code=204)
def delete_relationship(rel_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    rel = get_or_404(db, MemberRelationship, rel_id, tenant_id, "Relationship not found")
    rel.is_deleted = True
    db.commit()
