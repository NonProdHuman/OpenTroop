"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.base import Base, TrackedBase
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

__all__ = [
    "Base",
    "TrackedBase",
    "Member",
    "Patrol",
    "MemberRelationship",
    "Role",
    "RolePermission",
    "RoleMembership",
    "MemberRoleAssignment",
    "MemberStatus",
    "MemberType",
    "Permission",
    "SwimClassification",
    "RelationshipType",
]
