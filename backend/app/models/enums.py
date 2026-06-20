import enum


class MemberType(str, enum.Enum):
    """Whether a member is a youth participant or a registered adult."""

    SCOUT = "scout"
    ADULT = "adult"


class TroopRole(str, enum.Enum):
    """Position / title a member holds within the troop. Orthogonal to MemberType."""

    SCOUTMASTER = "scoutmaster"
    ASSISTANT_SCOUTMASTER = "assistant_scoutmaster"
    SENIOR_PATROL_LEADER = "senior_patrol_leader"
    PATROL_LEADER = "patrol_leader"
    TREASURER = "treasurer"
    COMMITTEE_CHAIR = "committee_chair"
    NONE = "none"


class SwimClassification(str, enum.Enum):
    """Official BSA aquatics classification."""

    NONSWIMMER = "nonswimmer"
    BEGINNER = "beginner"
    SWIMMER = "swimmer"


class RelationshipType(str, enum.Enum):
    """Nature of the adult -> scout guardian link."""

    PARENT = "parent"
    GUARDIAN = "guardian"
    OTHER = "other"
