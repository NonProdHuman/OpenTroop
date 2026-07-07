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
from app.models.consent import ConsentRecord
from app.models.enums import (
    AdvancementMode,
    CompletionStatus,
    ConsentMethod,
    ConsentScope,
    GroupType,
    ImportJobStatus,
    MemberStatus,
    MemberType,
    MetricKind,
    MetricWindow,
    Permission,
    PhotoStatus,
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
from app.models.event_photo import EventPhoto
from app.models.event_type import EventType
from app.models.group import Group, GroupMember, GroupRule
from app.models.import_job import ImportJob
from app.models.location import Location
from app.models.member import Member
from app.models.message import Message, MessageGroup, MessageRecipient
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
    "ConsentRecord",
    "ConsentScope",
    "ConsentMethod",
    "Event",
    "EventAudience",
    "EventPhoto",
    "EventOrganizer",
    "EventParticipant",
    "EventType",
    "Group",
    "PushToken",
    "GroupMember",
    "GroupRule",
    "ImportJob",
    "Location",
    "Member",
    "Message",
    "MessageGroup",
    "MessageRecipient",
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
    "ImportJobStatus",
    "MemberStatus",
    "MemberType",
    "Permission",
    "PhotoStatus",
    "PlatformRole",
    "PositionScope",
    "RsvpStatus",
    "RuleDimension",
    "RuleLogic",
    "SwimClassification",
    "RelationshipType",
]
