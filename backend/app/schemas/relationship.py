import uuid

from pydantic import BaseModel

from app.models.enums import RelationshipType
from app.schemas.base import TrackedRead


class MemberRelationshipBase(BaseModel):
    adult_id: uuid.UUID
    scout_id: uuid.UUID
    relationship_type: RelationshipType = RelationshipType.GUARDIAN


class MemberRelationshipCreate(MemberRelationshipBase):
    tenant_id: uuid.UUID


class MemberRelationshipUpdate(BaseModel):
    relationship_type: RelationshipType | None = None


class MemberRelationshipRead(MemberRelationshipBase, TrackedRead):
    pass
