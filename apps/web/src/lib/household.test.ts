/** Guards parity with the backend household rules in
 * `backend/app/core/relationships.py` (see its module docstring):
 * self ∪ children/wards ∪ co-parents, one hop through a shared child only. */

import { describe, expect, it } from "vitest"
import { householdIds, isDirectGuardian } from "./household"
import type { Member, MemberRelationship, RelationshipType } from "@/types/api"

let relId = 0
function rel(
  from: string,
  to: string,
  type: RelationshipType = "parent_of",
  isDeleted = false,
): MemberRelationship {
  return {
    id: `rel-${++relId}`,
    tenant_id: "t1",
    created_at: "",
    updated_at: "",
    is_deleted: isDeleted,
    from_member_id: from,
    to_member_id: to,
    relationship_type: type,
  }
}

function member(id: string, isDeleted = false): Member {
  return { id, is_deleted: isDeleted } as Member
}

describe("householdIds", () => {
  it("always includes the member themselves — a scout with no children collapses to {self}", () => {
    expect(householdIds("scout", [], [member("scout")])).toEqual(new Set(["scout"]))
  })

  it("includes children/wards via parent_of and guardian_of edges", () => {
    const rels = [rel("adult", "child1"), rel("adult", "ward1", "guardian_of")]
    const members = [member("adult"), member("child1"), member("ward1")]
    expect(householdIds("adult", rels, members)).toEqual(new Set(["adult", "child1", "ward1"]))
  })

  it("includes co-parents — another adult sharing one of my children", () => {
    const rels = [rel("adultA", "child"), rel("adultB", "child")]
    const members = [member("adultA"), member("adultB"), member("child")]
    expect(householdIds("adultA", rels, members)).toEqual(
      new Set(["adultA", "adultB", "child"]),
    )
  })

  it("is household-bounded, not transitive: a co-parent's other family stays out", () => {
    // A and B share child X; B also has child Y with co-parent C.
    // Y and C are NOT in A's household — one hop through a shared child only.
    const rels = [
      rel("adultA", "childX"),
      rel("adultB", "childX"),
      rel("adultB", "childY"),
      rel("adultC", "childY"),
    ]
    const members = ["adultA", "adultB", "adultC", "childX", "childY"].map((id) => member(id))
    expect(householdIds("adultA", rels, members)).toEqual(
      new Set(["adultA", "adultB", "childX"]),
    )
  })

  it("ignores sibling_of and other non-parental edges", () => {
    const rels = [rel("adult", "other", "sibling_of"), rel("adult", "friend", "other")]
    const members = [member("adult"), member("other"), member("friend")]
    expect(householdIds("adult", rels, members)).toEqual(new Set(["adult"]))
  })

  it("excludes soft-deleted members and soft-deleted relationships", () => {
    const rels = [
      rel("adult", "goneChild"),
      rel("adult", "exWard", "guardian_of", true), // deleted edge
    ]
    const members = [member("adult"), member("goneChild", true), member("exWard")]
    expect(householdIds("adult", rels, members)).toEqual(new Set(["adult"]))
  })

  it("excludes members missing from the roster entirely", () => {
    const rels = [rel("adult", "unknownChild")]
    expect(householdIds("adult", rels, [member("adult")])).toEqual(new Set(["adult"]))
  })
})

describe("isDirectGuardian", () => {
  it("is true only for a direct parent/guardian edge from actor to target", () => {
    const rels = [rel("adultA", "child"), rel("adultB", "child")]
    expect(isDirectGuardian("adultA", "child", rels)).toBe(true)
    expect(isDirectGuardian("adultB", "child", rels)).toBe(true)
    // Direction matters — the child is not the guardian of the parent.
    expect(isDirectGuardian("child", "adultA", rels)).toBe(false)
  })

  it("is false for a co-parent without their own edge over the child", () => {
    // B shares childX with A, but only A has an edge over childZ.
    const rels = [rel("adultA", "childX"), rel("adultB", "childX"), rel("adultA", "childZ")]
    expect(isDirectGuardian("adultB", "childZ", rels)).toBe(false)
  })

  it("ignores soft-deleted and non-parental edges", () => {
    const rels = [rel("adultA", "child", "parent_of", true), rel("adultB", "child", "sibling_of")]
    expect(isDirectGuardian("adultA", "child", rels)).toBe(false)
    expect(isDirectGuardian("adultB", "child", rels)).toBe(false)
  })
})
