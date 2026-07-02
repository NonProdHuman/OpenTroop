"use client"

import { Users } from "lucide-react"
import { householdIds } from "@/lib/household"
import { useSession } from "@/hooks/use-session"
import { useRelationships } from "@/hooks/use-relationships"
import { useMembers } from "@/hooks/use-members"
import { useEventParticipants, useTenantSettings } from "@/hooks/use-events"
import type { Event, Member } from "@/types/api"
import { MemberRsvpRow } from "./member-rsvp-row"

function memberName(m: Member) {
  return `${m.first_name} ${m.last_name}`
}

interface EventRsvpPanelProps {
  event: Event
}

export function EventRsvpPanel({ event }: EventRsvpPanelProps) {
  const { data: session } = useSession()
  const currentMember = session?.member

  const { data: allRelationships = [] } = useRelationships(currentMember?.id ?? null)
  const { data: allMembers = [] } = useMembers()
  const { data: participants = [] } = useEventParticipants(event.id)
  const { data: tenantSettings } = useTenantSettings()
  const permissionMessage =
    tenantSettings?.permission_message ?? "Permission is required for this event."

  if (!currentMember) return null
  if (!event.event_type.allow_signups) return null

  const memberById = new Map(allMembers.map((m) => [m.id, m]))
  const participantByMemberId = new Map(participants.map((p) => [p.member_id, p]))

  const household = householdIds(currentMember.id, allRelationships, allMembers)

  // The panel is a *self-service* surface: only the current member's household.
  // (Leader-facing attendee management lives on the event edit page, not here.)
  const familyMembers = [...household]
    .map((id) => memberById.get(id))
    .filter((m): m is Member => m !== undefined && !m.is_deleted)
    .sort((a, b) => {
      if (a.id === currentMember.id) return -1
      if (b.id === currentMember.id) return 1
      return memberName(a).localeCompare(memberName(b))
    })

  const goingCount = participants.filter((p) => p.rsvp_status === "going").length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          RSVP
        </h3>
        {goingCount > 0 && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            {goingCount} going
          </span>
        )}
      </div>

      <div className="space-y-2">
        {familyMembers.map((m) => (
          <MemberRsvpRow
            key={m.id}
            member={m}
            event={event}
            participant={participantByMemberId.get(m.id)}
            actorId={currentMember.id}
            relationships={allRelationships}
            permissionMessage={permissionMessage}
          />
        ))}
      </div>
    </div>
  )
}
