"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.base import Base, PlatformBase, TrackedBase
from app.models.enums import (
    MemberStatus,
    MemberType,
    Permission,
    RelationshipType,
    SwimClassification,
)
from app.models.member import Member
from app.models.patrol import Patrol
from app.models.relationship import MemberRelationship
from app.models.role import MemberRoleAssignment, Role, RoleMembership, RolePermission
from app.models.tenant import Tenant
from app.models.user import Identity, User

__all__ = [
    "Base",
    "PlatformBase",
    "TrackedBase",
    "Member",
    "Patrol",
    "MemberRelationship",
    "Role",
    "RolePermission",
    "RoleMembership",
    "MemberRoleAssignment",
    "Tenant",
    "User",
    "Identity",
    "MemberStatus",
    "MemberType",
    "Permission",
    "SwimClassification",
    "RelationshipType",
]
