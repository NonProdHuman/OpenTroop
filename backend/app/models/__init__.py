"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.advancement import (
    MemberMeritBadge,
    MemberRankProgress,
    MemberRequirementCompletion,
    MeritBadge,
    Rank,
    Requirement,
    RequirementSet,
)
from app.models.base import Base, PlatformBase, TrackedBase
from app.models.enums import (
    AdvancementMode,
    CompletionStatus,
    GroupType,
    MemberStatus,
    MemberType,
    MetricKind,
    MetricWindow,
    Permission,
    PlatformRole,
    PositionScope,
    RankCode,
    RecordedVia,
    RelationshipType,
    RsvpStatus,
    RuleDimension,
    RuleLogic,
    SwimClassification,
)
from app.models.event import Event, EventOrganizer, EventParticipant
from app.models.event_audience import EventAudience
from app.models.event_type import EventType
from app.models.group import Group, GroupMember, GroupRule
from app.models.location import Location
from app.models.member import Member
from app.models.push import PushToken
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from app.models.relationship import MemberRelationship
from app.models.tenant import Tenant
from app.models.user import Identity, User

__all__ = [
    "Base",
    "PlatformBase",
    "TrackedBase",
    "Event",
    "EventAudience",
    "EventOrganizer",
    "EventParticipant",
    "EventType",
    "Group",
    "PushToken",
    "GroupMember",
    "GroupRule",
    "Location",
    "Member",
    "MemberRelationship",
    "Position",
    "FunctionalRole",
    "FunctionalRolePermission",
    "PositionFunctionalRole",
    "MemberPositionAssignment",
    "Tenant",
    "User",
    "Identity",
    "Rank",
    "RequirementSet",
    "Requirement",
    "MeritBadge",
    "MemberRankProgress",
    "MemberRequirementCompletion",
    "MemberMeritBadge",
    "AdvancementMode",
    "CompletionStatus",
    "RecordedVia",
    "RankCode",
    "MetricKind",
    "MetricWindow",
    "GroupType",
    "MemberStatus",
    "MemberType",
    "Permission",
    "PlatformRole",
    "PositionScope",
    "RsvpStatus",
    "RuleDimension",
    "RuleLogic",
    "SwimClassification",
    "RelationshipType",
]
