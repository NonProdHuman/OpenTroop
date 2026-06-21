import enum


class MemberType(enum.StrEnum):
    """Whether a member is a youth participant or a registered adult."""

    SCOUT = "scout"
    ADULT = "adult"


class MemberStatus(enum.StrEnum):
    """Active participation state of a member.

    Distinct from ``is_deleted`` (sync tombstone). Alumni records remain visible
    to leaders for history and advancement lookups; deleted records are purged
    from sync payloads entirely.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"  # temporary break; still a member
    ALUMNI = "alumni"  # left the troop; data retained for history


class TroopRole(enum.StrEnum):
    """Current position a member holds within the troop. Orthogonal to MemberType.
    This is a convenience denormalization; authoritative history lives in
    LeadershipHistory (to be added in Pillar 1 CRUD work).
    """

    SCOUTMASTER = "scoutmaster"
    ASSISTANT_SCOUTMASTER = "assistant_scoutmaster"
    SENIOR_PATROL_LEADER = "senior_patrol_leader"
    PATROL_LEADER = "patrol_leader"
    ASSISTANT_PATROL_LEADER = "assistant_patrol_leader"
    TREASURER = "treasurer"
    COMMITTEE_CHAIR = "committee_chair"
    COMMITTEE_MEMBER = "committee_member"
    NONE = "none"


class SwimClassification(enum.StrEnum):
    """Official BSA aquatics classification."""

    NONSWIMMER = "nonswimmer"
    BEGINNER = "beginner"
    SWIMMER = "swimmer"


class RelationshipType(enum.StrEnum):
    """Nature of a relationship between two members.

    Directional for asymmetric types: ``from_member`` holds the role described.
    ``parent_of`` / ``guardian_of``: from_member is the adult; to_member is the youth.
    ``sibling_of``: symmetric; by convention store with the lower UUID as from_member.
    """

    PARENT_OF = "parent_of"
    GUARDIAN_OF = "guardian_of"  # legal/non-biological guardian
    SIBLING_OF = "sibling_of"  # symmetric
    OTHER = "other"
