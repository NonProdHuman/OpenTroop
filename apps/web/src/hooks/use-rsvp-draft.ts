"use client"

import { useEffect, useRef, useState } from "react"
import {
  useAddParticipant,
  useUpdateParticipant,
  type ParticipantBody,
} from "@/hooks/use-events"
import type { EventParticipant } from "@/types/api"

/** Local editable RSVP state for one member, persisted per-field.
 *
 * Shared by the self-service RSVP panel and the leader admin view, which edit
 * different subsets of the participant fields — `makeDraft` (a stable,
 * module-level function) picks the subset. Toggle/select fields persist
 * immediately (`setAndPersist`); text/number fields buffer locally (`setLocal`)
 * and persist on blur (`commitField`). The first write creates the participant
 * row if it doesn't exist yet.
 */
export function useRsvpDraft<T extends ParticipantBody & { comment: string }>(
  eventId: string,
  memberId: string,
  participant: EventParticipant | undefined,
  makeDraft: (participant: EventParticipant | undefined) => T,
) {
  const [draft, setDraft] = useState<T>(() => makeDraft(participant))

  // Re-seed local state from the server only when the participant *identity*
  // changes (initial load, or first creation). After that the local draft is the
  // source of truth so edits feel instant and aren't clobbered by refetches.
  const seededId = useRef<string | null>(participant?.id ?? null)
  useEffect(() => {
    if (participant && participant.id !== seededId.current) {
      seededId.current = participant.id
      setDraft(makeDraft(participant))
    }
  }, [participant, makeDraft])

  const addParticipant = useAddParticipant(eventId)
  const updateParticipant = useUpdateParticipant(eventId)

  /** Persist a partial change to the server (create the row if it doesn't exist yet). */
  function persist(changes: Partial<T>) {
    if (!participant) {
      addParticipant.mutate({
        member_id: memberId,
        rsvp_status: draft.rsvp_status,
        ...changes,
        comment: (changes.comment ?? draft.comment) || null,
      })
    } else {
      updateParticipant.mutate({
        memberId,
        ...changes,
        ...(changes.comment !== undefined ? { comment: changes.comment || null } : {}),
      })
    }
  }

  /** Toggle/select fields update local state and persist immediately. */
  function setAndPersist(changes: Partial<T>) {
    setDraft((d) => ({ ...d, ...changes }))
    persist(changes)
  }

  /** Text/number fields update local state on change; persist happens on blur. */
  function setLocal(changes: Partial<T>) {
    setDraft((d) => ({ ...d, ...changes }))
  }

  /** Commit a field on blur only if it differs from the server value. */
  function commitField(field: keyof T) {
    const serverDraft = makeDraft(participant)
    if (draft[field] !== serverDraft[field]) {
      persist({ [field]: draft[field] } as Partial<T>)
    }
  }

  return { draft, setAndPersist, setLocal, commitField }
}
