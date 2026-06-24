/** TypeScript mirror of the backend Pydantic schemas (app/schemas/). */

export type MemberType = "scout" | "adult"
export type MemberStatus = "active" | "inactive" | "alumni"
export type SwimClassification = "nonswimmer" | "beginner" | "swimmer"

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

  patrol_id: string | null
  user_id: string | null
}

export interface Patrol {
  id: string
  tenant_id: string
  created_at: string
  updated_at: string
  is_deleted: boolean
  name: string
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
