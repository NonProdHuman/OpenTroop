import { useMemo } from "react"
import { getRow, listRows } from "@/data/mirror"
import { overlayEvents, overlayParticipants } from "@/data/overlay"
import { listCommands } from "@/data/commands"
import { getMeta } from "@/data/schema"
import { useSyncContext } from "@/lib/sync-context"
import type { Event, EventParticipant, Member, MemberRelationship, Session } from "@/lib/types"

/**
 * Mirror-backed reads (GH-153): every screen reads the local database — the
 * network is never on the read path. Recomputes when the sync context's
 * version bumps (after a pull round, an enqueue, or a discard); pending
 * command effects are folded on top so offline changes show instantly.
 */

export function useMirrorEvents(): Event[] {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return []
    void version
    return overlayEvents(listRows<Event>(db, "events"), listCommands(db))
  }, [db, version])
}

export function useMirrorEvent(eventId: string): Event | null {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return null
    void version
    const row = getRow<Event>(db, "events", eventId)
    return row ? overlayEvents([row], listCommands(db))[0] : null
  }, [db, version, eventId])
}

export function useMirrorMembers(): Member[] {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return []
    void version
    return listRows<Member>(db, "members").sort((a, b) =>
      `${a.last_name}${a.first_name}`.localeCompare(`${b.last_name}${b.first_name}`),
    )
  }, [db, version])
}

export function useMirrorMember(memberId: string): Member | null {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return null
    void version
    return getRow<Member>(db, "members", memberId)
  }, [db, version, memberId])
}

export function useMirrorParticipants(eventId: string): EventParticipant[] {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return []
    void version
    const rows = listRows<EventParticipant>(db, "event_participants").filter(
      (p) => p.event_id === eventId,
    )
    return overlayParticipants(
      rows,
      listCommands(db).filter((c) => c.payload.event_id === eventId),
      (payload) =>
        ({
          id: "pending",
          event_id: String(payload.event_id),
          member_id: String(payload.member_id),
          signed_up: true,
          rsvp_status: "no_response",
          attended: null,
        }) as EventParticipant,
    )
  }, [db, version, eventId])
}

/**
 * The cached `/auth/session` snapshot (§C1) — offline UI affordances only;
 * the server re-checks every permission when a queued command replays.
 */
export function useCachedSession(): Session | null {
  const { db, version } = useSyncContext()
  return useMemo(() => {
    if (!db) return null
    void version
    const raw = getMeta(db, "session_snapshot")
    return raw ? (JSON.parse(raw) as Session) : null
  }, [db, version])
}

export function useCachedPermissions(): { has: (permission: string) => boolean } {
  const session = useCachedSession()
  const set = useMemo(() => new Set<string>(session?.permissions ?? []), [session])
  return { has: (permission: string) => set.has(permission) }
}

/** Me + my wards (parent/guardian edges) — who the RSVP section acts for. */
export function useMirrorFamily(): Member[] {
  const { db, version } = useSyncContext()
  const session = useCachedSession()
  return useMemo(() => {
    if (!db || !session?.member) return []
    void version
    const meId = session.member.id
    const wardIds = listRows<MemberRelationship>(db, "member_relationships")
      .filter(
        (r) =>
          r.from_member_id === meId &&
          (r.relationship_type === "parent_of" || r.relationship_type === "guardian_of"),
      )
      .map((r) => r.to_member_id)
    const byId = new Map(listRows<Member>(db, "members").map((m) => [m.id, m]))
    const me = byId.get(meId) ?? (session.member as Member)
    const wards = wardIds.map((id) => byId.get(id)).filter((m): m is Member => Boolean(m))
    return [me, ...wards]
  }, [db, version, session])
}
