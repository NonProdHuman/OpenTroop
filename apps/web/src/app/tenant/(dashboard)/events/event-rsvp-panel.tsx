"use client"

import { useState } from "react"
import { Check, ChevronDown, ChevronUp, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useSession } from "@/hooks/use-session"
import { useRelationships } from "@/hooks/use-relationships"
import { useMembers } from "@/hooks/use-members"
import {
  useEventParticipants,
  useAddParticipant,
  useUpdateParticipant,
  useGrantPermission,
  useTenantSettings,
} from "@/hooks/use-events"
import type {
  Event,
  EventParticipant,
  Member,
  MemberRelationship,
  RsvpStatus,
} from "@/types/api"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function memberName(m: Member) {
  return `${m.first_name} ${m.last_name}`
}

/** Derive the household the current member may RSVP for (mirrors backend logic). */
function householdIds(
  currentMemberId: string,
  relationships: MemberRelationship[],
  allMembers: Member[],
): Set<string> {
  const memberById = new Map(allMembers.map((m) => [m.id, m]))
  const children = new Set<string>()
  const coParents = new Set<string>()

  for (const rel of relationships) {
    const isParent =
      rel.from_member_id === currentMemberId &&
      (rel.relationship_type === "parent_of" || rel.relationship_type === "guardian_of")
    if (isParent) children.add(rel.to_member_id)
  }

  // Co-parents: adults who share one of my children
  for (const rel of relationships) {
    const isCoParent =
      children.has(rel.to_member_id) &&
      rel.from_member_id !== currentMemberId &&
      (rel.relationship_type === "parent_of" || rel.relationship_type === "guardian_of")
    if (isCoParent) coParents.add(rel.from_member_id)
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

/** Is this member a direct parent/guardian of the target? */
function isDirectGuardian(
  actorId: string,
  targetId: string,
  relationships: MemberRelationship[],
): boolean {
  return relationships.some(
    (r) =>
      r.from_member_id === actorId &&
      r.to_member_id === targetId &&
      (r.relationship_type === "parent_of" || r.relationship_type === "guardian_of") &&
      !r.is_deleted,
  )
}

// ---------------------------------------------------------------------------
// RSVP toggle row (one member)
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<RsvpStatus, string> = {
  no_response: "No response",
  going: "Going",
  declined: "Declined",
  maybe: "Maybe",
}

function RsvpStatusButtons({
  value,
  onChange,
  disabled,
}: {
  value: RsvpStatus
  onChange: (s: RsvpStatus) => void
  disabled?: boolean
}) {
  const options: RsvpStatus[] = ["going", "declined", "no_response"]
  return (
    <div className="flex gap-1">
      {options.map((s) => (
        <button
          key={s}
          type="button"
          disabled={disabled}
          onClick={() => onChange(s)}
          className={cn(
            "text-xs px-2 py-0.5 rounded-full border transition-colors",
            value === s
              ? s === "going"
                ? "bg-green-600 text-white border-green-600"
                : s === "declined"
                  ? "bg-destructive text-destructive-foreground border-destructive"
                  : "bg-muted border-muted-foreground text-foreground"
              : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
          )}
        >
          {STATUS_LABELS[s]}
        </button>
      ))}
    </div>
  )
}

function MemberRsvpRow({
  member,
  event,
  participant,
  actorId,
  relationships,
  isManager,
  permissionMessage,
}: {
  member: Member
  event: Event
  participant: EventParticipant | undefined
  actorId: string
  relationships: MemberRelationship[]
  isManager: boolean
  permissionMessage: string
}) {
  const [expanded, setExpanded] = useState(false)
  const [sigInput, setSigInput] = useState("")
  const [showPermDialog, setShowPermDialog] = useState(false)

  const addParticipant = useAddParticipant(event.id)
  const updateParticipant = useUpdateParticipant(event.id)
  const grantPermission = useGrantPermission(event.id)

  const isPending = addParticipant.isPending || updateParticipant.isPending
  const current = participant
  const rsvp: RsvpStatus = current?.rsvp_status ?? "no_response"
  const isScout = member.member_type === "scout"
  const needsSlip = event.event_type.require_permission_slip && isScout
  const slipStatus = current?.permission_status
  const canSign = isDirectGuardian(actorId, member.id, relationships)
  const allowGuests = event.event_type.allow_guests

  function mutate(updates: Partial<Parameters<typeof updateParticipant.mutate>[0]>) {
    if (!current) {
      addParticipant.mutate({
        member_id: member.id,
        rsvp_status: "no_response",
        ...updates,
      } as Parameters<typeof addParticipant.mutate>[0])
    } else {
      updateParticipant.mutate({
        memberId: member.id,
        ...updates,
      } as Parameters<typeof updateParticipant.mutate>[0])
    }
  }

  function handleRsvpChange(s: RsvpStatus) {
    mutate({ rsvp_status: s })
    if (s === "going" && needsSlip && canSign) {
      setShowPermDialog(true)
    }
  }

  function handleGrantPermission() {
    if (!sigInput.trim()) return
    grantPermission.mutate(
      { memberId: member.id, signature: sigInput.trim() },
      {
        onSuccess: () => {
          setShowPermDialog(false)
          setSigInput("")
        },
      },
    )
  }

  return (
    <div className="rounded-md border border-border p-3 space-y-2">
      {/* Top row: name + RSVP buttons */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{memberName(member)}</span>
          <span className="text-xs text-muted-foreground capitalize">{member.member_type}</span>
          {needsSlip && slipStatus === "pending" && rsvp === "going" && (
            <span className="text-xs text-amber-600 font-medium">Permission needed</span>
          )}
          {needsSlip && slipStatus === "granted" && (
            <span className="text-xs text-green-600 font-medium flex items-center gap-0.5">
              <Check className="h-3 w-3" />
              Permission granted
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RsvpStatusButtons value={rsvp} onChange={handleRsvpChange} disabled={isPending} />
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Toggle RSVP details"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Permission slip prompt (shown right after going is selected by a guardian) */}
      {showPermDialog && needsSlip && canSign && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3 space-y-2 text-sm">
          <p className="text-amber-800 font-medium">Permission required</p>
          <p className="text-amber-700 text-xs whitespace-pre-wrap">{permissionMessage}</p>
          <div className="space-y-1">
            <Label className="text-xs">Your name (electronic signature)</Label>
            <Input
              value={sigInput}
              onChange={(e) => setSigInput(e.target.value)}
              placeholder="Type your full name"
              className="h-7 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              className="h-7 text-xs"
              disabled={!sigInput.trim() || grantPermission.isPending}
              onClick={handleGrantPermission}
            >
              I Agree — Grant Permission
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => setShowPermDialog(false)}
            >
              Later
            </Button>
          </div>
        </div>
      )}

      {/* "Give permission" button shown to a guardian when slip is pending */}
      {!showPermDialog && needsSlip && slipStatus === "pending" && canSign && rsvp === "going" && (
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs"
          onClick={() => setShowPermDialog(true)}
        >
          Give permission for {member.first_name}
        </Button>
      )}

      {/* Expanded detail: drivers, guests, note */}
      {expanded && (
        <div className="space-y-3 pt-1 border-t border-border">
          {/* Driver section (adults, or managers viewing anyone) */}
          {(member.member_type === "adult" || isManager) && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={current?.driver ?? false}
                  onClick={() => mutate({ driver: !(current?.driver ?? false) })}
                  disabled={isPending}
                  className={cn(
                    "h-4 w-4 rounded border border-border flex items-center justify-center",
                    current?.driver && "bg-primary border-primary",
                  )}
                >
                  {current?.driver && <Check className="h-3 w-3 text-primary-foreground" />}
                </button>
                <Label className="text-xs cursor-pointer">Willing to drive</Label>
              </div>

              {current?.driver && (
                <div className="pl-6 space-y-2">
                  <div className="flex gap-4">
                    <label className="flex items-center gap-1.5 text-xs">
                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={current?.drives_to ?? false}
                        onClick={() => mutate({ drives_to: !(current?.drives_to ?? false) })}
                        disabled={isPending}
                        className={cn(
                          "h-3.5 w-3.5 rounded border border-border flex items-center justify-center",
                          current?.drives_to && "bg-primary border-primary",
                        )}
                      >
                        {current?.drives_to && (
                          <Check className="h-2.5 w-2.5 text-primary-foreground" />
                        )}
                      </button>
                      To event
                    </label>
                    <label className="flex items-center gap-1.5 text-xs">
                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={current?.drives_from ?? false}
                        onClick={() => mutate({ drives_from: !(current?.drives_from ?? false) })}
                        disabled={isPending}
                        className={cn(
                          "h-3.5 w-3.5 rounded border border-border flex items-center justify-center",
                          current?.drives_from && "bg-primary border-primary",
                        )}
                      >
                        {current?.drives_from && (
                          <Check className="h-2.5 w-2.5 text-primary-foreground" />
                        )}
                      </button>
                      From event
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs w-20 shrink-0">Seatbelts</Label>
                    <Input
                      type="number"
                      min={1}
                      max={15}
                      value={current?.seat_count ?? ""}
                      onChange={(e) =>
                        mutate({ seat_count: e.target.value ? Number(e.target.value) : null })
                      }
                      className="h-7 w-20 text-sm"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Guest count (only on allow_guests event types) */}
          {allowGuests && (
            <div className="flex items-center gap-2">
              <Label className="text-xs w-20 shrink-0">Guests</Label>
              <Input
                type="number"
                min={0}
                max={99}
                value={current?.guest_count ?? 0}
                onChange={(e) => mutate({ guest_count: Number(e.target.value) })}
                className="h-7 w-20 text-sm"
              />
              <span className="text-xs text-muted-foreground">non-roster attendees</span>
            </div>
          )}

          {/* Note */}
          <div className="space-y-1">
            <Label className="text-xs">Note</Label>
            <Textarea
              value={current?.comment ?? ""}
              onChange={(e) => mutate({ comment: e.target.value || null })}
              rows={2}
              placeholder="e.g. Arriving late Friday…"
              className="text-sm resize-none"
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

interface EventRsvpPanelProps {
  event: Event
}

export function EventRsvpPanel({ event }: EventRsvpPanelProps) {
  const { data: session } = useSession()
  const currentMember = session?.member
  const isManager = session?.permissions.includes("event:write") ?? false

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

  // Members to show: the current member's household, ordered self-first then by name
  const familyMembers = [...household]
    .map((id) => memberById.get(id))
    .filter((m): m is Member => m !== undefined && !m.is_deleted)
    .sort((a, b) => {
      if (a.id === currentMember.id) return -1
      if (b.id === currentMember.id) return 1
      return memberName(a).localeCompare(memberName(b))
    })

  // Managers also see all other participants not in their household
  const otherParticipantIds = isManager
    ? participants
        .map((p) => p.member_id)
        .filter((id) => !household.has(id))
    : []
  const otherParticipants = otherParticipantIds
    .map((id) => memberById.get(id))
    .filter((m): m is Member => m !== undefined)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          RSVP
        </h3>
        {participants.length > 0 && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            {participants.filter((p) => p.rsvp_status === "going").length} going
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
            isManager={isManager}
            permissionMessage={permissionMessage}
          />
        ))}

        {isManager && otherParticipants.length > 0 && (
          <>
            <p className="text-xs text-muted-foreground pt-1">Other participants</p>
            {otherParticipants.map((m) => (
              <MemberRsvpRow
                key={m.id}
                member={m}
                event={event}
                participant={participantByMemberId.get(m.id)}
                actorId={currentMember.id}
                relationships={allRelationships}
                isManager={isManager}
                permissionMessage={permissionMessage}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
