/**
 * Pure advancement helpers — payload builders, date validation, queue filtering,
 * and action-visibility rules. Kept free of React/React Native so the Node
 * vitest suite can exercise the workflow logic that the online advancement
 * screen drives. UI wiring lives in the advancement tab; the backend re-checks
 * every permission.
 */

import type { AdvancementQueue, Completion, CompletionStatus, MeritBadge } from "./types"

/** A YYYY-MM-DD date, the only format the completion/badge/rank inputs accept. */
export const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function isValidDate(value: string): boolean {
  return DATE_RE.test(value.trim())
}

/** Create-completion body; a blank note collapses to omitted (matches web). */
export function buildCompletionPayload(input: {
  requirementId: string
  dateCompleted: string
  note?: string
}): { requirement_id: string; date_completed: string; note?: string } {
  const note = input.note?.trim()
  return {
    requirement_id: input.requirementId,
    date_completed: input.dateCompleted,
    ...(note ? { note } : {}),
  }
}

/** Record-merit-badge body; a blank completion date collapses to omitted. */
export function buildMeritBadgePayload(input: {
  meritBadgeId: string
  dateCompleted?: string
}): { merit_badge_id: string; date_completed?: string } {
  const date = input.dateCompleted?.trim()
  return {
    merit_badge_id: input.meritBadgeId,
    ...(date ? { date_completed: date } : {}),
  }
}

/** Edit-merit-badge body; a blank completion date clears it (null), moving the
 *  badge back to in-progress. `status` is included only when provided. */
export function buildMeritBadgeUpdate(input: {
  dateCompleted: string
  status?: CompletionStatus
}): { date_completed: string | null; status?: CompletionStatus } {
  const date = input.dateCompleted.trim()
  return {
    date_completed: date || null,
    ...(input.status ? { status: input.status } : {}),
  }
}

/** Rank BOR / awarded date body; blank inputs clear the field (null). */
export function buildRankDatesPayload(input: {
  completedDate: string
  awardedDate: string
}): { completed_date: string | null; awarded_date: string | null } {
  return {
    completed_date: input.completedDate.trim() || null,
    awarded_date: input.awardedDate.trim() || null,
  }
}

/**
 * Which completion actions render for a given completion.
 * Mirrors the web inline actions: approve/reject a *reported* completion for
 * approvers; revoke a *recorded* (non-reported) completion for approvers or
 * recorders. Nothing is offered once the rank is awarded (locked).
 */
export function completionActions(opts: {
  status: CompletionStatus | null
  canApprove: boolean
  canRecord: boolean
  locked: boolean
}): { showApproveReject: boolean; showRevoke: boolean } {
  if (!opts.status || opts.locked) {
    return { showApproveReject: false, showRevoke: false }
  }
  return {
    showApproveReject: opts.status === "reported" && opts.canApprove,
    showRevoke: opts.status !== "reported" && (opts.canApprove || opts.canRecord),
  }
}

/** Catalog badges a member may still be recorded for (not earned, not discontinued). */
export function availableBadges(catalog: MeritBadge[], earned: Set<string>): MeritBadge[] {
  return catalog.filter((b) => !earned.has(b.id) && !b.is_discontinued)
}

/** Case-insensitive name search over the catalog picker. */
export function filterBadgeCatalog(catalog: MeritBadge[], query: string): MeritBadge[] {
  const q = query.trim().toLowerCase()
  if (!q) return catalog
  return catalog.filter((b) => b.name.toLowerCase().includes(q))
}

/** Reported completions awaiting approval (queue endpoint already scopes to pending). */
export function pendingCompletions(queue: AdvancementQueue | undefined): Completion[] {
  return (queue?.completions ?? []).filter((c) => c.status === "reported")
}

export function pendingMeritBadges(queue: AdvancementQueue | undefined) {
  return (queue?.merit_badges ?? []).filter((b) => b.status === "reported")
}

/** Total items awaiting approval — drives the "Needs approval" chip count. */
export function pendingQueueCount(queue: AdvancementQueue | undefined): number {
  return pendingCompletions(queue).length + pendingMeritBadges(queue).length
}
