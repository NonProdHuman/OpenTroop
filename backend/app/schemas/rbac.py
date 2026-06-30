import uuid
from datetime import date

from pydantic import BaseModel, computed_field

from app.core.permissions import is_assignment_current
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
    # Defaults to today in the router when omitted; end_date set means a closed term.
    start_date: date | None = None
    end_date: date | None = None


class MemberPositionAssignmentUpdate(BaseModel):
    """Edit a term's dates. Fields left unset are untouched; passing ``end_date: null``
    explicitly reopens a closed term (the router applies ``exclude_unset``)."""

    start_date: date | None = None
    end_date: date | None = None


class MemberPositionAssignmentRead(TrackedRead):
    member_id: uuid.UUID
    position_id: uuid.UUID
    assigned_by_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_current(self) -> bool:
        """Whether this term is live now — the single currency rule, Python side."""
        return is_assignment_current(self.is_deleted, self.end_date)
