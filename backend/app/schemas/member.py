import uuid

from pydantic import BaseModel, EmailStr

from app.models.enums import MemberType, SwimClassification, TroopRole
from app.schemas.base import TrackedRead


class MemberBase(BaseModel):
    bsa_id: str | None = None
    first_name: str
    last_name: str
    email: EmailStr | None = None
    phone: str | None = None
    member_type: MemberType
    troop_role: TroopRole = TroopRole.NONE
    swim_classification: SwimClassification = SwimClassification.NONSWIMMER
    patrol_id: uuid.UUID | None = None


class MemberCreate(MemberBase):
    tenant_id: uuid.UUID


class MemberUpdate(BaseModel):
    bsa_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    member_type: MemberType | None = None
    troop_role: TroopRole | None = None
    swim_classification: SwimClassification | None = None
    patrol_id: uuid.UUID | None = None


class MemberRead(MemberBase, TrackedRead):
    pass
