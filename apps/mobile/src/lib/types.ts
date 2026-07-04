/** Thin aliases into the shared generated API types — never hand-write shapes. */

import type { components } from "@opentroop/api-types"

type Schemas = components["schemas"]

export type Membership = Schemas["MembershipRead"]
export type Session = Schemas["SessionRead"]
export type EventParticipant = Schemas["EventParticipantRead"]
export type MemberRelationship = Schemas["MemberRelationshipRead"]
export type AdvancementScout = Schemas["AdvancementScoutRead"]
export type MemberAdvancement = Schemas["MemberAdvancementRead"]
export type MemberRankView = Schemas["MemberRankView"]
export type RequirementProgress = Schemas["RequirementProgress"]
export type MeritBadge = Schemas["MeritBadgeRead"]
export type TenantSettings = Schemas["TenantSettingsRead"]
export type Member = Schemas["MemberRead"]
export type Event = Schemas["EventRead"]
export type EventType = Schemas["EventTypeRead"]
