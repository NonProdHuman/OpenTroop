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


class Permission(enum.StrEnum):
    """All capabilities that can be granted to a Role.

    Colon-namespaced by domain. Relationship-scoped access (e.g. a parent reading
    their own child's record) is enforced separately at the endpoint layer; these
    permissions gate whether the action is possible at all.
    """

    # Member management
    MEMBER_READ = "member:read"
    MEMBER_WRITE = "member:write"
    MEMBER_READ_MEDICAL = "member:read_medical"
    MEMBER_WRITE_MEDICAL = "member:write_medical"
    MEMBER_READ_CONTACT = "member:read_contact"
    MEMBER_DELETE = "member:delete"

    # Event management
    EVENT_READ = "event:read"
    EVENT_CREATE = "event:create"
    EVENT_WRITE = "event:write"
    EVENT_DELETE = "event:delete"
    EVENT_MANAGE_ATTENDANCE = "event:manage_attendance"

    # Advancement
    ADVANCEMENT_READ = "advancement:read"
    ADVANCEMENT_RECORD = "advancement:record"
    ADVANCEMENT_APPROVE = "advancement:approve"

    # Finance
    FINANCE_READ = "finance:read"
    FINANCE_WRITE = "finance:write"

    # Role management
    ROLE_ASSIGN = "role:assign"
    ROLE_MANAGE = "role:manage"

    # Communications
    COMMUNICATION_SEND_TROOP = "communication:send_troop"
    COMMUNICATION_SEND_PATROL = "communication:send_patrol"

    # Reports
    REPORT_READ = "report:read"


class GroupType(enum.StrEnum):
    """How a Group's membership is primarily managed.

    MANUAL  — members are added and removed explicitly.
    DYNAMIC — membership is computed from rules (e.g. role-based).
    PATROL  — the roster's unit-of-belonging: a manual group a member belongs to
              at most one of. Folds the former standalone Patrol model.

    Resolution always unions manual inclusions with any rule-derived members,
    regardless of type; the type is a management/UI hint, not a hard switch.
    """

    MANUAL = "manual"
    DYNAMIC = "dynamic"
    PATROL = "patrol"


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


class PlatformRole(enum.StrEnum):
    """Global (cross-tenant) role held by a platform User.

    Distinct from tenant-scoped RBAC (Role / Permission), which governs what a
    member can do *inside one troop*. A platform role governs the SaaS control
    plane: creating/suspending tenants and administering tenant admins. Most
    users have no platform role (``User.platform_role is None``).

    SUPERADMIN — full platform control (create tenants, manage tenant admins).
    SUPPORT    — read-oriented operator access for troubleshooting (future use).
    BILLING    — billing/subscription administration (future use).
    """

    SUPERADMIN = "superadmin"
    SUPPORT = "support"
    BILLING = "billing"
