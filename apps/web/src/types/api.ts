/**
 * Backend API types.
 *
 * These are **thin aliases** into `api.generated.ts`, which is generated from the
 * FastAPI OpenAPI spec by `pnpm gen:api`. Do NOT hand-write shapes here — change the
 * backend Pydantic schema, run `pnpm gen:api`, then (if you added a new schema) add an
 * alias below. CI fails if the committed generated file drifts from the backend.
 *
 * The alias names are the frontend-facing vocabulary (`Member`, `Event`, …); the
 * right-hand side is the backend schema component (`MemberRead`, `EventRead`, …).
 */

import type { components } from "./api.generated"

type Schemas = components["schemas"]

// ── Enums (string unions) ─────────────────────────────────────────────────────

export type MemberType = Schemas["MemberType"]
export type MemberStatus = Schemas["MemberStatus"]
export type SwimClassification = Schemas["SwimClassification"]
export type RelationshipType = Schemas["RelationshipType"]
export type RsvpStatus = Schemas["RsvpStatus"]
export type PermissionSlipStatus = Schemas["PermissionSlipStatus"]
export type PositionScope = Schemas["PositionScope"]
export type GroupType = Schemas["GroupType"]
export type RuleLogic = Schemas["RuleLogic"]
export type RuleDimension = Schemas["RuleDimension"]
export type Permission = Schemas["Permission"]
export type PlatformRole = Schemas["PlatformRole"]

// ── Members & relationships ───────────────────────────────────────────────────

export type Member = Schemas["MemberRead"]
export type MemberRelationship = Schemas["MemberRelationshipRead"]
export type Family = Schemas["FamilyRead"]
export type AnnouncementEmailMode = Schemas["AnnouncementEmailMode"]
export type NotificationPreferences = Schemas["NotificationPreferencesRead"]
export type NotificationPreferencesUpdate = Schemas["NotificationPreferencesUpdate"]

// ── RBAC ──────────────────────────────────────────────────────────────────────

export type Position = Schemas["PositionRead"]
export type FunctionalRole = Schemas["FunctionalRoleRead"]
export type FunctionalRolePermission = Schemas["FunctionalRolePermissionRead"]
export type PositionFunctionalRole = Schemas["PositionFunctionalRoleRead"]
export type MemberPositionAssignment = Schemas["MemberPositionAssignmentRead"]

// ── Groups ────────────────────────────────────────────────────────────────────

export type Group = Schemas["GroupRead"]
export type GroupRule = Schemas["GroupRuleRead"]
/** An explicit (manual) group membership row — distinct from rule-derived members. */
export type GroupMemberRow = Schemas["GroupMemberRead"]
/** One group's fully resolved membership — the unit of GET /groups/roster. */
export type GroupRosterEntry = Schemas["GroupRosterEntry"]

// ── Events ────────────────────────────────────────────────────────────────────

export type EventType = Schemas["EventTypeRead"]
export type Event = Schemas["EventRead"]
export type Location = Schemas["LocationRead"]
export type EventParticipant = Schemas["EventParticipantRead"]
export type EventParticipantCounts = Schemas["EventParticipantCounts"]
export type EventAudience = Schemas["EventAudienceRead"]
export type EventPhoto = Schemas["EventPhotoWithUrl"]
export type PhotoUploadTarget = Schemas["PhotoUploadTarget"]
export type PhotoInitiateItem = Schemas["PhotoInitiateItem"]
export type PhotoInitiateResponse = Schemas["PhotoInitiateResponse"]
export type PhotoDownload = Schemas["PhotoDownload"]
export type StorageUsage = Schemas["StorageUsageRead"]
export type EventOrganizer = Schemas["EventOrganizerRead"]
export type EventSlot = Schemas["EventSlotRead"]
export type EventSlotSignup = Schemas["EventSlotSignupRead"]
export type EventSlotCreate = Schemas["EventSlotCreate"]
export type EventSlotUpdate = Schemas["EventSlotUpdate"]

// ── Tenant settings ───────────────────────────────────────────────────────────

export type TenantSettings = Schemas["TenantSettingsRead"]

// ── Session & permissions ─────────────────────────────────────────────────────

export type SessionRole = Schemas["SessionRoleRead"]
export type Session = Schemas["SessionRead"]

// ── Platform (global) control plane ───────────────────────────────────────────

export type User = Schemas["UserRead"]
export type Tenant = Schemas["TenantRead"]
export type TenantProvisioned = Schemas["TenantProvisioned"]
export type TenantProvisionInput = Schemas["TenantProvision"]
export type TenantAdmin = Schemas["TenantAdminRead"]
export type TenantAdminInviteInput = Schemas["TenantAdminInvite"]
export type TenantAdminInviteResult = Schemas["TenantAdminInviteResult"]
export type PlatformAdmin = Schemas["PlatformAdminRead"]
export type PlatformAdminGrantInput = Schemas["PlatformAdminGrant"]
export type TenantDeleteInput = Schemas["TenantDeleteRequest"]

// ── Hard delete (GH-222) ──────────────────────────────────────────────────────

export type MemberPurgeInput = Schemas["MemberPurgeRequest"]

// ── Calendar ──────────────────────────────────────────────────────────────────

export type CalendarSubscriptionRead = Schemas["CalendarSubscriptionRead"]

// ── Tenant switcher ───────────────────────────────────────────────────────────

export type Membership = Schemas["MembershipRead"]

// ── Import ────────────────────────────────────────────────────────────────────

export type ImportJob = Schemas["ImportJobRead"]

// ── Advancement (Pillar 4, GH-92) ─────────────────────────────────────────────

export type AdvancementMode = Schemas["AdvancementMode"]
export type CompletionStatus = Schemas["CompletionStatus"]
export type RecordedVia = Schemas["RecordedVia"]
export type Rank = Schemas["RankRead"]
export type RankWithSets = Schemas["RankWithSets"]
export type RequirementSet = Schemas["RequirementSetRead"]
export type RequirementSetDetail = Schemas["RequirementSetDetail"]
export type Requirement = Schemas["RequirementRead"]
export type MeritBadge = Schemas["MeritBadgeRead"]
export type Completion = Schemas["CompletionRead"]
export type MemberMeritBadge = Schemas["MemberMeritBadgeRead"]
export type RankProgress = Schemas["RankProgressRead"]
export type MemberAdvancement = Schemas["MemberAdvancementRead"]
export type MemberRankView = Schemas["MemberRankView"]
export type RequirementProgress = Schemas["RequirementProgress"]
export type MetricProgress = Schemas["MetricProgress"]
export type AdvancementQueue = Schemas["AdvancementQueueRead"]

export type AdvancementScout = Schemas["AdvancementScoutRead"]

// ── Messaging (Pillar 5, GH-146) ──────────────────────────────────────────────
export type Message = Schemas["MessageRead"]
export type MessageCreate = Schemas["MessageCreate"]
export type MessageWithPreview = Schemas["MessageWithPreview"]
export type MessageDetail = Schemas["MessageDetail"]
export type MessageRecipient = Schemas["MessageRecipientRead"]
export type AudiencePreview = Schemas["AudiencePreview"]
export type RecipientPreviewEntry = Schemas["RecipientPreviewEntry"]
export type RecipientPreview = Schemas["RecipientPreview"]
export type RecipientPreviewRequest = Schemas["RecipientPreviewRequest"]
export type MessageGroupTarget = Schemas["MessageGroupTarget"]
export type MessageDelivery = Schemas["MessageDelivery"]
export type InboxPage = Schemas["InboxPage"]
export type InboxEntry = Schemas["InboxEntry"]
export type AudienceType = Schemas["AudienceType"]
export type ElectionResult = Schemas["ElectionResult"]

// ── Reports (#147) ────────────────────────────────────────────────────────────
export type ReportCatalogEntry = Schemas["ReportCatalogEntry"]
export type ReportParamSchema = Schemas["ReportParamSchema"]
export type ReportParamOption = Schemas["ReportParamOption"]
export type ReportColumn = Schemas["ReportColumnSchema"]
export type ReportData = Schemas["ReportData"]
/** One report cell value (derived from the generated row shape). */
export type ReportValue = ReportData["rows"][number][string]
