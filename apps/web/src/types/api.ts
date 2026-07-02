/** TypeScript mirror of the backend Pydantic schemas (app/schemas/). */

export type MemberType = "scout" | "adult"
export type MemberStatus = "active" | "inactive" | "alumni"
export type SwimClassification = "nonswimmer" | "beginner" | "swimmer"
export type RelationshipType = "parent_of" | "guardian_of" | "sibling_of" | "other"
export type RsvpStatus = "no_response" | "going" | "declined" | "maybe"
export type PermissionSlipStatus = "not_required" | "pending" | "granted"

export interface Member {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean

  bsa_id: string | null
  first_name: string
  middle_name: string | null
  last_name: string
  name_suffix: string | null
  nickname: string | null
  date_of_birth: string | null // ISO date "YYYY-MM-DD"

  email: string | null
  phone: string | null

  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  postal_code: string | null
  country: string | null

  member_type: MemberType
  membership_status: MemberStatus
  swim_classification: SwimClassification

  troop_membership_start_date: string | null
  troop_membership_end_date: string | null
  swim_date: string | null
  medical_form_ab_date: string | null
  medical_form_c_date: string | null

  allergies: string | null
  dietary_restrictions: string | null

  emergency_contact_1_name: string | null
  emergency_contact_1_phone: string | null
  emergency_contact_2_name: string | null
  emergency_contact_2_phone: string | null

  email_opt_out: boolean
  email_bounced: boolean
  sms_opt_in: boolean

  notes: string | null

  oa_member: boolean
  oa_active: boolean
  oa_election_date: string | null
  oa_call_out_date: string | null
  oa_ordeal_date: string | null
  oa_brotherhood_date: string | null
  oa_vigil_date: string | null
  oa_vigil_name: string | null
  oa_notes: string | null

  user_id: string | null
}

// ── RBAC ─────────────────────────────────────────────────────────────────────

export type PositionScope = "scout" | "adult" | "any"

export interface Position {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  slug: string
  applies_to: PositionScope
  sort_order: number
  is_system: boolean
  is_default: boolean
}

export interface FunctionalRole {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  slug: string
  is_system: boolean
  is_admin: boolean
}

export interface FunctionalRolePermission {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  functional_role_id: string
  permission: Permission
}

export interface PositionFunctionalRole {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  position_id: string
  functional_role_id: string
}

export interface MemberPositionAssignment {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  member_id: string
  position_id: string
  assigned_by_id: string | null
  // A term: held from start_date to an optional end_date (null = open-ended).
  start_date: string | null
  end_date: string | null
  // Derived server-side from the currency rule (not is_deleted and not ended).
  is_current: boolean
}

// ── Relationships ─────────────────────────────────────────────────────────────

export interface MemberRelationship {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  from_member_id: string
  to_member_id: string
  relationship_type: RelationshipType
}

// ── Groups ───────────────────────────────────────────────────────────────────
// A Group is the unifying "set of members" primitive. Patrols are folded in as
// PATROL-type groups; membership is manual and/or rule-driven (see backend
// app/models/group.py).

export type GroupType = "custom" | "patrol"
export type RuleLogic = "and" | "or"
export type RuleDimension =
  | "member_type"
  | "membership_status"
  | "oa_member"
  | "oa_active"
  | "position"
  | "group_member"
  | "rank"

export interface Group {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  description: string | null
  group_type: GroupType
  color: string | null
  is_system: boolean
  rule_logic: RuleLogic
  include_parents: boolean
  cc_parents_on_messages: boolean
}

export interface GroupRule {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  group_id: string
  dimension: RuleDimension
  values: string[] | null
}

// An explicit (manual) group membership row — distinct from rule-derived members.
export interface GroupMemberRow {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  group_id: string
  member_id: string
  added_by_id: string | null
}

// One group's fully resolved membership — the unit of GET /groups/roster.
export interface GroupRosterEntry {
  group_id: string
  member_ids: string[]
}

// ── Events ───────────────────────────────────────────────────────────────────

export interface EventType {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  color: string | null
  is_active: boolean
  is_system: boolean
  tracks_service_hours: boolean
  tracks_camping_nights: boolean
  tracks_mileage: boolean
  allow_signups: boolean
  require_permission_slip: boolean
  allow_guests: boolean
  is_online: boolean
}

export interface EventParticipant {
  id: string
  tenant_id: string
  event_id: string
  member_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  signed_up: boolean
  rsvp_status: RsvpStatus
  attended: boolean | null
  guest_count: number
  driver: boolean
  drives_to: boolean
  drives_from: boolean
  seat_count: number | null
  comment: string | null
  signed_up_at: string | null
  hiking_miles_override: string | null
  backpacking_miles_override: string | null
  paddling_miles_override: string | null
  cycling_miles_override: string | null
  community_service_hours_override: string | null
  conservation_hours_override: string | null
  water_hours_override: string | null
  camping_nights_override: number | null
  permission_slip_submitted: boolean
  electronic_permission: boolean
  electronic_permission_at: string | null
  electronic_permission_by_id: string | null
  electronic_permission_signature: string | null
  permission_message_snapshot: string | null
  permission_status: PermissionSlipStatus
}

export interface EventParticipantCounts {
  scouts: number
  adults: number
  drivers: number
  guests: number
}

export interface EventAudience {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  event_id: string
  group_id: string
}

export interface EventOrganizer {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  event_id: string
  member_id: string
}

export interface TenantSettings {
  permission_message: string
}

export interface Location {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  street1: string | null
  street2: string | null
  city: string | null
  state: string | null
  postal_code: string | null
  country: string | null
  phone: string | null
  website_url: string | null
  directions: string | null
  description: string | null
  distance_miles: number | null
}

export interface Event {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  event_type_id: string
  location_id: string | null
  location_notes: string | null
  departure_location: string | null
  return_location: string | null
  scheduled_start: string // ISO datetime
  scheduled_end: string // ISO datetime
  all_day: boolean
  signup_start: string | null
  signup_deadline: string | null
  signup_limit_scouts: number | null
  signup_limit_adults: number | null
  cost_youth: string | null // Decimal serialized as string
  cost_adult: string | null
  video_conference_url: string | null
  description: string | null
  agenda: string | null
  tour_permit_submitted: boolean | null
  attendance_taken: boolean
  linked_event_id: string | null
  community_service_hours: string | null
  conservation_hours: string | null
  hiking_miles: string | null
  backpacking_miles: string | null
  paddling_miles: string | null
  cycling_miles: string | null
  water_hours: string | null
  camping_nights: number | null
  event_type: EventType
  location: Location | null
}

// ── Session & Permissions ─────────────────────────────────────────────────────

export type Permission =
  | "member:read"
  | "member:write"
  | "member:read_medical"
  | "member:write_medical"
  | "member:read_contact"
  | "member:delete"
  | "event:read"
  | "event:create"
  | "event:write"
  | "event:delete"
  | "event:manage_attendance"
  | "advancement:read"
  | "advancement:record"
  | "advancement:approve"
  | "finance:read"
  | "finance:write"
  | "role:assign"
  | "role:manage"
  | "communication:send_troop"
  | "communication:send_patrol"
  | "report:read"

export interface SessionRole {
  id: string
  name: string
}

export interface Session {
  tenant_id: string
  member: Member | null
  permissions: Permission[]
  roles: SessionRole[]
}

// ── Platform (global) control plane ──────────────────────────────────────────

export type PlatformRole = "superadmin" | "support" | "billing"

export interface User {
  id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  email: string | null
  display_name: string | null
  platform_role: PlatformRole | null
}

export interface Tenant {
  id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
  slug: string
  suspended_at: string | null
}

export interface TenantProvisioned extends Tenant {
  founder_member_id: string
  invite_token: string
  invite_expires_at: string
}

export interface TenantProvisionInput {
  name: string
  slug: string
  founder_first_name: string
  founder_last_name: string
  founder_email?: string | null
}

export interface TenantAdmin {
  member_id: string
  first_name: string
  last_name: string
  email: string | null
  user_id: string | null
  claimed: boolean
}

export interface TenantAdminInviteInput {
  first_name: string
  last_name: string
  email?: string | null
}

export interface TenantAdminInviteResult {
  member_id: string
  token: string
  expires_at: string
}

export interface PlatformAdmin {
  user_id: string
  email: string | null
  display_name: string | null
  platform_role: PlatformRole
}

export interface PlatformAdminGrantInput {
  email: string
  role: PlatformRole
}

export interface CalendarSubscriptionRead {
  token: string
  feed_path: string
}

// ── Tenant switcher ───────────────────────────────────────────────────────────

export interface Membership {
  tenant_id: string
  tenant_name: string
  tenant_slug: string
  member_id: string
  is_admin: boolean
}

export interface TwhImportRead {
  patrols: number
  members: number
  relationships: number
  locations: number
  event_types: number
  events: number
  participants: number
  skipped: number
  warnings: string[]
}
