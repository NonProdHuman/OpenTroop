import uuid

from pydantic import BaseModel

from app.models.enums import Permission
from app.schemas.base import TrackedRead


class RoleBase(BaseModel):
    name: str
    slug: str
    is_system: bool = False
    is_admin: bool = False


class RoleCreate(RoleBase):
    tenant_id: uuid.UUID


class RoleUpdate(BaseModel):
    name: str | None = None


class RoleRead(RoleBase, TrackedRead):
    pass


class RolePermissionBase(BaseModel):
    role_id: uuid.UUID
    permission: Permission


class RolePermissionCreate(RolePermissionBase):
    tenant_id: uuid.UUID


class RolePermissionRead(RolePermissionBase, TrackedRead):
    pass


class RoleMembershipBase(BaseModel):
    group_role_id: uuid.UUID
    member_role_id: uuid.UUID


class RoleMembershipCreate(RoleMembershipBase):
    tenant_id: uuid.UUID


class RoleMembershipRead(RoleMembershipBase, TrackedRead):
    pass


class MemberRoleAssignmentBase(BaseModel):
    member_id: uuid.UUID
    role_id: uuid.UUID
    assigned_by_id: uuid.UUID | None = None


class MemberRoleAssignmentCreate(MemberRoleAssignmentBase):
    tenant_id: uuid.UUID


class MemberRoleAssignmentRead(MemberRoleAssignmentBase, TrackedRead):
    pass
