import uuid

from pydantic import BaseModel

from app.models.enums import Permission, PositionScope
from app.schemas.base import TrackedRead

# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


class PositionBase(BaseModel):
    name: str
    slug: str
    applies_to: PositionScope = PositionScope.ANY
    sort_order: int = 0


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    name: str | None = None
    applies_to: PositionScope | None = None
    sort_order: int | None = None


class PositionRead(PositionBase, TrackedRead):
    is_system: bool


# ---------------------------------------------------------------------------
# Functional roles
# ---------------------------------------------------------------------------


class FunctionalRoleBase(BaseModel):
    name: str
    slug: str


class FunctionalRoleCreate(FunctionalRoleBase):
    pass


class FunctionalRoleUpdate(BaseModel):
    name: str | None = None


class FunctionalRoleRead(FunctionalRoleBase, TrackedRead):
    is_system: bool
    is_admin: bool


class FunctionalRolePermissionRead(TrackedRead):
    functional_role_id: uuid.UUID
    permission: Permission


# ---------------------------------------------------------------------------
# Mapping + assignment
# ---------------------------------------------------------------------------


class PositionFunctionalRoleRead(TrackedRead):
    position_id: uuid.UUID
    functional_role_id: uuid.UUID


class FunctionalRoleLinkCreate(BaseModel):
    functional_role_id: uuid.UUID


class MemberPositionAssignmentCreate(BaseModel):
    position_id: uuid.UUID
    assigned_by_id: uuid.UUID | None = None


class MemberPositionAssignmentRead(TrackedRead):
    member_id: uuid.UUID
    position_id: uuid.UUID
    assigned_by_id: uuid.UUID | None = None
