/** Family-relationship resolution for RSVP authorization.
 *
 * Mirrors the backend's `app/core/relationships.py` — the household a member may
 * act for is `{self} ∪ children/wards ∪ co-parents`, derived from the directional
 * `parent_of` / `guardian_of` edges. The closure is household-bounded, not
 * transitive: one hop through a shared child only. `household.test.ts` guards
 * parity with the backend rules.
 */

import type { Member, MemberRelationship } from "@/types/api"

function isParentEdge(rel: MemberRelationship): boolean {
  return (
    !rel.is_deleted &&
    (rel.relationship_type === "parent_of" || rel.relationship_type === "guardian_of")
  )
}

/** Derive the household the current member may RSVP for. */
export function householdIds(
  currentMemberId: string,
  relationships: MemberRelationship[],
  allMembers: Member[],
): Set<string> {
  const memberById = new Map(allMembers.map((m) => [m.id, m]))
  const children = new Set<string>()
  const coParents = new Set<string>()

  for (const rel of relationships) {
    if (rel.from_member_id === currentMemberId && isParentEdge(rel)) {
      children.add(rel.to_member_id)
    }
  }

  // Co-parents: adults who share one of my children
  for (const rel of relationships) {
    if (
      children.has(rel.to_member_id) &&
      rel.from_member_id !== currentMemberId &&
      isParentEdge(rel)
    ) {
      coParents.add(rel.from_member_id)
    }
  }

  const ids = new Set([currentMemberId, ...children, ...coParents])
  // Filter out deleted members
  for (const id of ids) {
    if (id !== currentMemberId) {
      const m = memberById.get(id)
      if (!m || m.is_deleted) ids.delete(id)
    }
  }
  return ids
}

/** Is this member a direct parent/guardian of the target?
 *
 * Stricter than household membership — mirrors the backend's `is_guardian_of`,
 * which gates signing a permission slip (a co-parent without a direct edge
 * over the child may not sign).
 */
export function isDirectGuardian(
  actorId: string,
  targetId: string,
  relationships: MemberRelationship[],
): boolean {
  return relationships.some(
    (r) => r.from_member_id === actorId && r.to_member_id === targetId && isParentEdge(r),
  )
}
