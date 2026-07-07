import { describe, expect, it } from "vitest"
import {
  availableBadges,
  buildCompletionPayload,
  buildMeritBadgePayload,
  buildMeritBadgeUpdate,
  buildRankDatesPayload,
  completionActions,
  filterBadgeCatalog,
  isValidDate,
  pendingCompletions,
  pendingMeritBadges,
  pendingQueueCount,
} from "./advancement"
import type { AdvancementQueue, Completion, MemberMeritBadge, MeritBadge } from "./types"

describe("isValidDate", () => {
  it("accepts a YYYY-MM-DD date, trimming whitespace", () => {
    expect(isValidDate("2026-07-07")).toBe(true)
    expect(isValidDate("  2026-07-07  ")).toBe(true)
  })
  it("rejects other shapes", () => {
    expect(isValidDate("")).toBe(false)
    expect(isValidDate("2026-7-7")).toBe(false)
    expect(isValidDate("07/07/2026")).toBe(false)
  })
})

describe("buildCompletionPayload", () => {
  it("omits a blank note", () => {
    expect(
      buildCompletionPayload({ requirementId: "r1", dateCompleted: "2026-07-07", note: "   " }),
    ).toEqual({ requirement_id: "r1", date_completed: "2026-07-07" })
  })
  it("includes and trims a note", () => {
    expect(
      buildCompletionPayload({ requirementId: "r1", dateCompleted: "2026-07-07", note: " ok " }),
    ).toEqual({ requirement_id: "r1", date_completed: "2026-07-07", note: "ok" })
  })
})

describe("buildMeritBadgePayload", () => {
  it("omits a blank date", () => {
    expect(buildMeritBadgePayload({ meritBadgeId: "b1", dateCompleted: "" })).toEqual({
      merit_badge_id: "b1",
    })
  })
  it("includes a date", () => {
    expect(buildMeritBadgePayload({ meritBadgeId: "b1", dateCompleted: "2026-07-07" })).toEqual({
      merit_badge_id: "b1",
      date_completed: "2026-07-07",
    })
  })
})

describe("buildMeritBadgeUpdate", () => {
  it("clears a blank date to null and omits status when absent", () => {
    expect(buildMeritBadgeUpdate({ dateCompleted: "" })).toEqual({ date_completed: null })
  })
  it("carries date and status", () => {
    expect(buildMeritBadgeUpdate({ dateCompleted: "2026-07-07", status: "approved" })).toEqual({
      date_completed: "2026-07-07",
      status: "approved",
    })
  })
})

describe("buildRankDatesPayload", () => {
  it("maps blanks to null and keeps dates", () => {
    expect(buildRankDatesPayload({ completedDate: "2026-07-07", awardedDate: "" })).toEqual({
      completed_date: "2026-07-07",
      awarded_date: null,
    })
  })
})

describe("completionActions", () => {
  it("offers approve/reject for a reported completion to an approver", () => {
    expect(
      completionActions({ status: "reported", canApprove: true, canRecord: false, locked: false }),
    ).toEqual({ showApproveReject: true, showRevoke: false })
  })
  it("offers revoke for an approved completion to a recorder", () => {
    expect(
      completionActions({ status: "approved", canApprove: false, canRecord: true, locked: false }),
    ).toEqual({ showApproveReject: false, showRevoke: true })
  })
  it("shows nothing once the rank is locked (awarded)", () => {
    expect(
      completionActions({ status: "approved", canApprove: true, canRecord: true, locked: true }),
    ).toEqual({ showApproveReject: false, showRevoke: false })
  })
  it("shows nothing without permission", () => {
    expect(
      completionActions({ status: "reported", canApprove: false, canRecord: false, locked: false }),
    ).toEqual({ showApproveReject: false, showRevoke: false })
  })
})

const badge = (id: string, name: string, extra: Partial<MeritBadge> = {}): MeritBadge =>
  ({ id, name, eagle_required: false, is_discontinued: false, ...extra }) as MeritBadge

describe("availableBadges", () => {
  it("drops earned and discontinued badges", () => {
    const catalog = [
      badge("a", "Camping"),
      badge("b", "Basketry", { is_discontinued: true }),
      badge("c", "Cooking"),
    ]
    const result = availableBadges(catalog, new Set(["c"]))
    expect(result.map((b) => b.id)).toEqual(["a"])
  })
})

describe("filterBadgeCatalog", () => {
  const catalog = [badge("a", "Camping"), badge("b", "Cooking"), badge("c", "First Aid")]
  it("returns all for an empty query", () => {
    expect(filterBadgeCatalog(catalog, "  ")).toHaveLength(3)
  })
  it("matches case-insensitively", () => {
    expect(filterBadgeCatalog(catalog, "coo").map((b) => b.id)).toEqual(["b"])
  })
})

const completion = (id: string, status: Completion["status"], memberId = "m1"): Completion =>
  ({ id, status, member_id: memberId, date_completed: "2026-07-07" }) as Completion
const memberBadge = (id: string, status: MemberMeritBadge["status"]): MemberMeritBadge =>
  ({ id, status, member_id: "m1", merit_badge_id: "b1" }) as MemberMeritBadge

describe("queue filtering", () => {
  const queue: AdvancementQueue = {
    completions: [completion("c1", "reported"), completion("c2", "approved")],
    merit_badges: [memberBadge("b1", "reported"), memberBadge("b2", "reported")],
  }
  it("keeps only reported completions", () => {
    expect(pendingCompletions(queue).map((c) => c.id)).toEqual(["c1"])
  })
  it("keeps reported merit badges", () => {
    expect(pendingMeritBadges(queue).map((b) => b.id)).toEqual(["b1", "b2"])
  })
  it("counts total pending items", () => {
    expect(pendingQueueCount(queue)).toBe(3)
  })
  it("is zero for an undefined queue", () => {
    expect(pendingQueueCount(undefined)).toBe(0)
  })
})
