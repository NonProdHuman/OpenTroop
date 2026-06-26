import uuid

from pydantic import BaseModel

from app.models.enums import GroupType
from app.schemas.base import TrackedRead


class GroupBase(BaseModel):
    name: str
    description: str | None = None
    group_type: GroupType = GroupType.MANUAL
    color: str | None = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    group_type: GroupType | None = None
    color: str | None = None


class GroupRead(GroupBase, TrackedRead):
    is_system: bool


class GroupMemberCreate(BaseModel):
    member_id: uuid.UUID


class GroupMemberRead(TrackedRead):
    group_id: uuid.UUID
    member_id: uuid.UUID
    added_by_id: uuid.UUID | None = None


class GroupPositionRuleCreate(BaseModel):
    position_id: uuid.UUID


class GroupPositionRuleRead(TrackedRead):
    group_id: uuid.UUID
    position_id: uuid.UUID
