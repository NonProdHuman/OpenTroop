"use client"

import { Clock, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatDateTime, formatMemberName } from "@/lib/format"
import { householdIds } from "@/lib/household"
import { useSession } from "@/hooks/use-session"
import { useRelationships } from "@/hooks/use-relationships"
import { useMembers } from "@/hooks/use-members"
import { useEventSlots, useJoinSlot, useLeaveSlot } from "@/hooks/use-event-slots"
import type { Event, EventSlot, Member } from "@/types/api"

interface EventSlotsPanelProps {
  event: Event
}

/** Whether a slot's `applies_to` scope admits this member's type. */
function eligible(slot: EventSlot, member: Member): boolean {
  return slot.applies_to === "any" || slot.applies_to === member.member_type
}

function slotWindow(slot: EventSlot): string | null {
  if (!slot.starts_at) return null
  const start = formatDateTime(slot.starts_at)
  const end = slot.ends_at ? formatDateTime(slot.ends_at) : null
  return end ? `${start} → ${end}` : start
}

export function EventSlotsPanel({ event }: EventSlotsPanelProps) {
  const { data: session } = useSession()
  const currentMember = session?.member

  const { data: slots = [] } = useEventSlots(event.id)
  const { data: allRelationships = [] } = useRelationships(currentMember?.id ?? null)
  const { data: allMembers = [] } = useMembers()
  const join = useJoinSlot(event.id)
  const leave = useLeaveSlot(event.id)

  if (!currentMember) return null
  // Empty state is hidden — nothing to sign up for.
  if (slots.length === 0) return null

  const memberById = new Map(allMembers.map((m) => [m.id, m]))
  const household = householdIds(currentMember.id, allRelationships, allMembers)
  const familyMembers = [...household]
    .map((id) => memberById.get(id))
    .filter((m): m is Member => m !== undefined && !m.is_deleted)
    .sort((a, b) => {
      if (a.id === currentMember.id) return -1
      if (b.id === currentMember.id) return 1
      return formatMemberName(a).localeCompare(formatMemberName(b))
    })

  return (
    <div className="space-y-4" data-testid="event-slots-panel">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Sign-up slots
      </h3>

      <div className="space-y-3">
        {slots.map((slot) => {
          const signedUpIds = new Set(slot.signups.map((s) => s.member_id))
          const isFull = slot.remaining === 0
          const window = slotWindow(slot)
          return (
            <div
              key={slot.id}
              className="rounded-lg border border-border p-3 space-y-2"
              data-testid={`slot-${slot.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{slot.name}</p>
                  {window && (
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {window}
                    </p>
                  )}
                  {slot.description && (
                    <p className="text-xs text-muted-foreground">{slot.description}</p>
                  )}
                </div>
                <span
                  className="shrink-0 text-xs text-muted-foreground flex items-center gap-1"
                  data-testid={`slot-fill-${slot.id}`}
                >
                  <Users className="h-3.5 w-3.5" />
                  {slot.capacity === null
                    ? `${slot.signups.length} signed up`
                    : `${slot.signups.length} of ${slot.capacity}`}
                </span>
              </div>

              {slot.signups.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {slot.signups.map((s) => s.member_name).join(", ")}
                </p>
              )}

              <div className="flex flex-wrap gap-1.5">
                {familyMembers.map((m) => {
                  if (!eligible(slot, m)) return null
                  const joined = signedUpIds.has(m.id)
                  const label = m.id === currentMember.id ? "Me" : formatMemberName(m)
                  if (joined) {
                    return (
                      <Button
                        key={m.id}
                        size="sm"
                        variant="outline"
                        data-testid={`slot-leave-${slot.id}-${m.id}`}
                        disabled={leave.isPending}
                        onClick={() => leave.mutate({ slotId: slot.id, memberId: m.id })}
                      >
                        Leave · {label}
                      </Button>
                    )
                  }
                  return (
                    <Button
                      key={m.id}
                      size="sm"
                      variant="secondary"
                      data-testid={`slot-join-${slot.id}-${m.id}`}
                      disabled={isFull || join.isPending}
                      onClick={() => join.mutate({ slotId: slot.id, memberId: m.id })}
                    >
                      {isFull ? "Full" : `Sign up · ${label}`}
                    </Button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
