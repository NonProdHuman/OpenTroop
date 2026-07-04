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

    CUSTOM — the general-purpose group: members may be added explicitly *and/or*
             resolved from dynamic rules. The two are unioned.
    PATROL — the roster's unit-of-belonging: a manual group a member belongs to
             at most one of (adults excluded). Patrols carry no rules. Folds the
             former standalone Patrol model.

    Resolution always unions manual inclusions with any rule-derived members; the
    type is a management/UI hint plus the patrol one-per-member constraint.
    """

    CUSTOM = "custom"
    PATROL = "patrol"


class RuleLogic(enum.StrEnum):
    """How a group's dynamic rules combine to produce the resolved member set.

    AND — a member must match *all* rules (intersection). Default. Each rule
          narrows the set — "active scouts who are OA members".
    OR  — a member matching *any* rule is included (union). Each rule broadens
          the set — "adults or leadership-position holders".

    Manual members (``GroupMember`` rows) are always included regardless of
    rule logic.
    """

    AND = "and"
    OR = "or"


class RuleDimension(enum.StrEnum):
    """Dimensions available for dynamic group membership rules.

    Each dimension targets one aspect of a member's data. A group has at most
    one rule per dimension; multiple values for a dimension (e.g. several
    positions) are stored as a JSON list in ``GroupRule.values``.
    """

    MEMBER_TYPE = "member_type"
    MEMBERSHIP_STATUS = "membership_status"
    OA_MEMBER = "oa_member"
    OA_ACTIVE = "oa_active"
    POSITION = "position"
    GROUP_MEMBER = "group_member"
    RANK = "rank"  # current rank (highest completed) — see app/core/groups.py


class CompletionStatus(enum.StrEnum):
    """Workflow state of a reported advancement completion (GH-92).

    REPORTED — entered by a scout/parent (mode ``scout_reported``); awaiting the
               advancement chair's approval.
    APPROVED — counts toward the rank. Direct chair entry and auto-credits are
               born approved.
    REJECTED — reviewed and declined; may be re-reported with new evidence.

    Revocation is the soft-delete tombstone, not a status — a revoked auto-credit
    must never be re-created by the engine, which treats any existing row
    (including deleted) as "do not re-create".
    """

    REPORTED = "reported"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecordedVia(enum.StrEnum):
    """How an advancement completion row came to exist (GH-92)."""

    MANUAL = "manual"  # entered by a person (self-report or chair entry)
    AUTO = "auto"  # auto-credit engine crossed a metric threshold
    IMPORT = "import"  # Scoutbook import
    REMAP = "remap"  # copied across requirement sets on a version-election switch


class AdvancementMode(enum.StrEnum):
    """Per-tenant switch for the advancement workflow (GH-92).

    DISABLED       — nav hidden; advancement endpoints 404; auto-credit inert.
    CHAIR_ENTRY    — only ``advancement:record`` holders write; entries are born
                     approved. The default for new tenants.
    SCOUT_REPORTED — scouts/parents self-report; the approval queue is active.
    """

    DISABLED = "disabled"
    CHAIR_ENTRY = "chair_entry"
    SCOUT_REPORTED = "scout_reported"


class RankCode(enum.StrEnum):
    """The seven sequential Scouts BSA ranks (Pillar 4, see GH-92).

    Scout–First Class may be worked simultaneously but are earned in sequence;
    ordering lives on ``Rank.sort_order``, this enum is the stable identifier.
    Eagle Palms are deferred (not a rank row).
    """

    SCOUT = "scout"
    TENDERFOOT = "tenderfoot"
    SECOND_CLASS = "second_class"
    FIRST_CLASS = "first_class"
    STAR = "star"
    LIFE = "life"
    EAGLE = "eagle"


class MetricKind(enum.StrEnum):
    """Countable quantity a catalog requirement can be measured against (GH-92).

    Stored in ``Requirement.metrics`` JSON conditions; each maps to data OpenTroop
    already tracks (event activity metrics × attendance, position terms, merit
    badges, rank dates). See ``app/core/advancement.py`` (Phase 3) for evaluation.
    """

    CAMPING_NIGHTS = "camping_nights"
    SERVICE_HOURS = "service_hours"
    CONSERVATION_HOURS = "conservation_hours"
    HIKING_MILES = "hiking_miles"
    ACTIVITY_COUNT = "activity_count"
    TENURE_MONTHS = "tenure_months"
    POR_MONTHS = "por_months"
    MERIT_BADGE_COUNT = "merit_badge_count"
    MERIT_BADGE_COUNT_EAGLE_REQUIRED = "merit_badge_count_eagle_required"


class MetricWindow(enum.StrEnum):
    """Time window a metric condition accumulates over (GH-92).

    ANY           — all recorded history.
    SINCE_JOINING — anchored at the member's troop joining (fallback: earliest
                    attendance).
    SINCE_RANK    — anchored at the previous rank's board-of-review date
                    (``MemberRankProgress.completed_date``).
    """

    ANY = "any"
    SINCE_JOINING = "since_joining"
    SINCE_RANK = "since_rank"


class PositionScope(enum.StrEnum):
    """Which kind of member a Position may be assigned to.

    A UI/validation hint, not a hard wall: ``ANY`` positions (e.g. a custom
    troop role) apply to both. Scout positions (Patrol Leader) vs adult
    positions (Scoutmaster) are filtered by this when assigning.
    """

    SCOUT = "scout"
    ADULT = "adult"
    ANY = "any"


class SwimClassification(enum.StrEnum):
    """Official BSA aquatics classification."""

    NONSWIMMER = "nonswimmer"
    BEGINNER = "beginner"
    SWIMMER = "swimmer"


class RsvpStatus(enum.StrEnum):
    """A member's explicit response to an event invitation.

    Distinct from ``EventParticipant.signed_up`` (the roster/headcount flag) and
    ``attended`` (post-event actuals): ``rsvp_status`` is the member-facing reply.

    NO_RESPONSE — invited / on the list but hasn't replied (the default).
    GOING       — will attend.
    DECLINED    — will not attend; grayed out in the app and omitted from the
                  member's personal iCal feed.
    MAYBE       — tentative.
    """

    NO_RESPONSE = "no_response"
    GOING = "going"
    DECLINED = "declined"
    MAYBE = "maybe"


class PermissionSlipStatus(enum.StrEnum):
    """Derived status of a scout's parental permission slip for an event.

    Not stored — computed from the event type, the scout's RSVP, and whether a
    parent has signed under the *current* tenant permission language. See
    ``app.core.permission_slip`` and ``docs/spec/event-rsvp-permission.md``.

    NOT_REQUIRED — the event type doesn't require a slip, or the scout isn't going.
    PENDING      — required and the scout is going, but no valid signature yet.
    GRANTED      — a parent/guardian has signed under the current language.
    """

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    GRANTED = "granted"


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
