/**
 * Central React Query key factory.
 *
 * Every tenant-scoped key is prefixed with the active tenant id so switching
 * tenants can never serve another tenant's cache. Using these functions instead
 * of inline arrays makes keys greppable and typo-proof — a mistyped string in an
 * `invalidateQueries` call silently never matches (that exact bug existed: the
 * session key was written in two different orders, so assigning a position never
 * refreshed the caller's permission set).
 *
 * Item keys extend their collection key (`[t, "groups"]` → `[t, "groups", id]`),
 * so invalidating the collection also invalidates every item via prefix matching.
 */

type TenantId = string | null

export const queryKeys = {
  // ── Tenant-independent ────────────────────────────────────────────────────
  me: () => ["me"] as const,
  memberships: () => ["memberships"] as const,
  calendarSubscription: () => ["calendar-subscription"] as const,

  // ── Session (per tenant) ──────────────────────────────────────────────────
  session: (t: TenantId) => [t, "session"] as const,

  // ── Members ───────────────────────────────────────────────────────────────
  members: (t: TenantId) => [t, "members"] as const,
  member: (t: TenantId, id: string | null) => [t, "members", id] as const,
  relationships: (t: TenantId, memberId: string | null) => [t, "relationships", memberId] as const,

  // ── Groups ────────────────────────────────────────────────────────────────
  groups: (t: TenantId) => [t, "groups"] as const,
  group: (t: TenantId, id: string | null) => [t, "groups", id] as const,
  groupRoster: (t: TenantId) => [t, "group-roster"] as const,
  groupMembers: (t: TenantId, groupId?: string | null) =>
    groupId === undefined ? ([t, "group-members"] as const) : ([t, "group-members", groupId] as const),
  groupManualMembers: (t: TenantId, groupId?: string | null) =>
    groupId === undefined
      ? ([t, "group-manual-members"] as const)
      : ([t, "group-manual-members", groupId] as const),
  groupRules: (t: TenantId, groupId: string | null) => [t, "group-rules", groupId] as const,

  // ── RBAC ──────────────────────────────────────────────────────────────────
  positions: (t: TenantId) => [t, "positions"] as const,
  position: (t: TenantId, id: string | null) => [t, "positions", id] as const,
  positionFunctionalRoles: (t: TenantId, positionId: string | null) =>
    [t, "position-functional-roles", positionId] as const,
  functionalRoles: (t: TenantId) => [t, "functional-roles"] as const,
  functionalRole: (t: TenantId, id: string | null) => [t, "functional-roles", id] as const,
  functionalRolePermissions: (t: TenantId, roleId: string | null) =>
    [t, "functional-role-permissions", roleId] as const,
  memberPositions: (t: TenantId, memberId: string | null, history?: boolean) =>
    history === undefined
      ? ([t, "member-positions", memberId] as const)
      : ([t, "member-positions", memberId, history ? "history" : "current"] as const),

  // ── Events ────────────────────────────────────────────────────────────────
  events: (t: TenantId) => [t, "events"] as const,
  event: (t: TenantId, id: string | null) => [t, "events", id] as const,
  eventTypes: (t: TenantId) => [t, "event-types"] as const,
  eventType: (t: TenantId, id: string | null) => [t, "event-types", id] as const,
  eventParticipants: (t: TenantId, eventId: string | null) => [t, "event-participants", eventId] as const,
  eventCounts: (t: TenantId, eventId: string | null) => [t, "event-counts", eventId] as const,
  eventAudiences: (t: TenantId, eventId: string | null) => [t, "event-audiences", eventId] as const,
  eventOrganizers: (t: TenantId, eventId: string | null) => [t, "event-organizers", eventId] as const,
  eventPhotos: (t: TenantId, eventId: string | null) => [t, "event-photos", eventId] as const,
  eventSlots: (t: TenantId, eventId: string | null) => [t, "event-slots", eventId] as const,
  storageUsage: (t: TenantId) => [t, "storage-usage"] as const,
  locations: (t: TenantId) => [t, "locations"] as const,

  // ── Advancement ───────────────────────────────────────────────────────────
  advancementRanks: (t: TenantId) => [t, "advancement-ranks"] as const,
  meritBadges: (t: TenantId) => [t, "merit-badges"] as const,
  memberAdvancement: (t: TenantId, memberId: string | null) =>
    [t, "member-advancement", memberId] as const,
  advancementQueue: (t: TenantId) => [t, "advancement-queue"] as const,
  advancementScouts: (t: TenantId) => [t, "advancement-scouts"] as const,

  // ── Messaging ─────────────────────────────────────────────────────────────
  messages: (t: TenantId) => [t, "messages"] as const,
  message: (t: TenantId, id: string | null) => [t, "message", id] as const,
  messagePreview: (t: TenantId, id: string | null) => [t, "message-preview", id] as const,
  inbox: (t: TenantId) => [t, "inbox"] as const,

  // ── Tenant settings ───────────────────────────────────────────────────────
  tenantSettings: (t: TenantId) => [t, "tenant-settings"] as const,

  // ── Reports (#147) ────────────────────────────────────────────────────────
  reportCatalog: (t: TenantId) => [t, "report-catalog"] as const,
  report: (t: TenantId, key: string, params: Record<string, string>) =>
    [t, "report", key, params] as const,
}
