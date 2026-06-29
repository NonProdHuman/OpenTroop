import uuid

from pydantic import BaseModel

from app.models.enums import GroupType, RuleDimension, RuleLogic
from app.schemas.base import TrackedRead


class GroupBase(BaseModel):
    name: str
    description: str | None = None
    group_type: GroupType = GroupType.CUSTOM
    color: str | None = None
    rule_logic: RuleLogic = RuleLogic.AND
    include_parents: bool = False
    cc_parents_on_messages: bool = False


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    group_type: GroupType | None = None
    color: str | None = None
    rule_logic: RuleLogic | None = None
    include_parents: bool | None = None
    cc_parents_on_messages: bool | None = None


class GroupRead(GroupBase, TrackedRead):
    is_system: bool


class GroupMemberCreate(BaseModel):
    member_id: uuid.UUID


class GroupMemberRead(TrackedRead):
    group_id: uuid.UUID
    member_id: uuid.UUID
    added_by_id: uuid.UUID | None = None


class GroupRuleUpsert(BaseModel):
    """Body for PUT /groups/{id}/rules/{dimension}."""

    values: list[str] | None = None


class GroupRuleRead(TrackedRead):
    group_id: uuid.UUID
    dimension: RuleDimension
    values: list[str] | None = None
