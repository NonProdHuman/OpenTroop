"use client"

import { useEffect, useRef, useState } from "react"
import { AlertTriangle, Check, ChevronDown, ChevronUp, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
// Local editable state for one member's RSVP
// ---------------------------------------------------------------------------

type RsvpDraft = {
  rsvp_status: RsvpStatus
  driver: boolean
  drives_to: boolean
  drives_from: boolean
  seat_count: number | null
  guest_count: number
  comment: string
}

function draftFrom(participant: EventParticipant | undefined): RsvpDraft {
  return {
    rsvp_status: participant?.rsvp_status ?? "no_response",
    driver: participant?.driver ?? false,
    drives_to: participant?.drives_to ?? false,
    drives_from: participant?.drives_from ?? false,
    seat_count: participant?.seat_count ?? null,
    guest_count: participant?.guest_count ?? 0,
    comment: participant?.comment ?? "",
  }
}

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

function CheckboxButton({
  checked,
  onToggle,
  disabled,
  size = "md",
  label,
}: {
  checked: boolean
  onToggle: () => void
  disabled?: boolean
  size?: "sm" | "md"
  label: string
}) {
  const box = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"
  const tick = size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        box,
        "rounded border border-border flex items-center justify-center shrink-0",
        checked && "bg-primary border-primary",
      )}
    >
      {checked && <Check className={cn(tick, "text-primary-foreground")} />}
    </button>
  )
}

function MemberRsvpRow({
  member,
  event,
  participant,
  actorId,
  relationships,
  permissionMessage,
}: {
  member: Member
  event: Event
  participant: EventParticipant | undefined
  actorId: string
  relationships: MemberRelationship[]
  permissionMessage: string
}) {
  const [expanded, setExpanded] = useState(false)
  const [sigInput, setSigInput] = useState("")
  const [showPermDialog, setShowPermDialog] = useState(false)
  const [draft, setDraft] = useState<RsvpDraft>(() => draftFrom(participant))

  // Re-seed local state from the server only when the participant *identity*
  // changes (initial load, or first creation). After that the local draft is the
  // source of truth so edits feel instant and aren't clobbered by refetches.
  const seededId = useRef<string | null>(participant?.id ?? null)
  useEffect(() => {
    if (participant && participant.id !== seededId.current) {
      seededId.current = participant.id
      setDraft(draftFrom(participant))
    }
  }, [participant])

  const addParticipant = useAddParticipant(event.id)
  const updateParticipant = useUpdateParticipant(event.id)
  const grantPermission = useGrantPermission(event.id)

  const isScout = member.member_type === "scout"
  const needsSlip = event.event_type.require_permission_slip && isScout
  const slipStatus = participant?.permission_status
  const canSign = isDirectGuardian(actorId, member.id, relationships)
  const allowGuests = event.event_type.allow_guests

  /** Persist a partial change to the server (create the row if it doesn't exist yet). */
  function persist(changes: Partial<RsvpDraft>) {
    if (!participant) {
      addParticipant.mutate({
        member_id: member.id,
        rsvp_status: draft.rsvp_status,
        ...changes,
        comment: (changes.comment ?? draft.comment) || null,
      })
    } else {
      updateParticipant.mutate({
        memberId: member.id,
        ...changes,
        ...(changes.comment !== undefined ? { comment: changes.comment || null } : {}),
      })
    }
  }

  /** Toggle/select fields update local state and persist immediately. */
  function setAndPersist(changes: Partial<RsvpDraft>) {
    setDraft((d) => ({ ...d, ...changes }))
    persist(changes)
  }

  /** Text/number fields update local state on change; persist happens on blur. */
  function setLocal(changes: Partial<RsvpDraft>) {
    setDraft((d) => ({ ...d, ...changes }))
  }

  /** Commit a field on blur only if it differs from the server value. */
  function commitField(field: keyof RsvpDraft) {
    const serverDraft = draftFrom(participant)
    if (draft[field] !== serverDraft[field]) {
      persist({ [field]: draft[field] } as Partial<RsvpDraft>)
    }
  }

  function handleRsvpChange(s: RsvpStatus) {
    setAndPersist({ rsvp_status: s })
    if (s === "going" && needsSlip && canSign && slipStatus !== "granted") {
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
          {needsSlip && slipStatus === "pending" && draft.rsvp_status === "going" && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
              <AlertTriangle className="h-3 w-3" />
              Permission needed
            </span>
          )}
          {needsSlip && slipStatus === "granted" && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-800">
              <Check className="h-3 w-3" />
              Permission granted
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <RsvpStatusButtons value={draft.rsvp_status} onChange={handleRsvpChange} />
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
      {needsSlip && canSign && (
        <Dialog open={showPermDialog} onOpenChange={setShowPermDialog}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Permission required for {member.first_name}
              </DialogTitle>
            </DialogHeader>
            <div className="max-h-[50vh] overflow-y-auto rounded-md border border-border bg-muted/30 p-3">
              <p className="text-foreground text-sm leading-relaxed whitespace-pre-wrap">
                {permissionMessage}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-medium">Your name (electronic signature)</Label>
              <Input
                value={sigInput}
                onChange={(e) => setSigInput(e.target.value)}
                placeholder="Type your full name"
                className="h-9 text-sm"
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowPermDialog(false)}>
                Later
              </Button>
              <Button
                className="bg-green-700 hover:bg-green-800 text-white"
                disabled={!sigInput.trim() || grantPermission.isPending}
                onClick={handleGrantPermission}
              >
                <Check className="h-3.5 w-3.5 mr-1" />
                I Agree — Grant Permission
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* "Give permission" button shown to a guardian when slip is pending */}
      {!showPermDialog &&
        needsSlip &&
        slipStatus === "pending" &&
        canSign &&
        draft.rsvp_status === "going" && (
          <Button
            size="sm"
            className="h-8 text-xs bg-amber-600 hover:bg-amber-700 text-white"
            onClick={() => setShowPermDialog(true)}
          >
            <AlertTriangle className="h-3 w-3 mr-1" />
            Give permission for {member.first_name}
          </Button>
        )}

      {/* Expanded detail: drivers, guests, note */}
      {expanded && (
        <div className="space-y-3 pt-1 border-t border-border">
          {/* Driver section (adults only — scouts don't drive) */}
          {member.member_type === "adult" && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <CheckboxButton
                  checked={draft.driver}
                  onToggle={() => setAndPersist({ driver: !draft.driver })}
                  label="Willing to drive"
                />
                <Label className="text-xs cursor-pointer">Willing to drive</Label>
              </div>

              {draft.driver && (
                <div className="pl-6 space-y-2">
                  <div className="flex gap-4">
                    <label className="flex items-center gap-1.5 text-xs">
                      <CheckboxButton
                        size="sm"
                        checked={draft.drives_to}
                        onToggle={() => setAndPersist({ drives_to: !draft.drives_to })}
                        label="Drives to event"
                      />
                      To event
                    </label>
                    <label className="flex items-center gap-1.5 text-xs">
                      <CheckboxButton
                        size="sm"
                        checked={draft.drives_from}
                        onToggle={() => setAndPersist({ drives_from: !draft.drives_from })}
                        label="Drives from event"
                      />
                      From event
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs w-20 shrink-0">Seatbelts</Label>
                    <Input
                      type="number"
                      min={1}
                      max={15}
                      value={draft.seat_count ?? ""}
                      onChange={(e) =>
                        setLocal({ seat_count: e.target.value ? Number(e.target.value) : null })
                      }
                      onBlur={() => commitField("seat_count")}
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
                value={draft.guest_count}
                onChange={(e) => setLocal({ guest_count: Number(e.target.value) || 0 })}
                onBlur={() => commitField("guest_count")}
                className="h-7 w-20 text-sm"
              />
              <span className="text-xs text-muted-foreground">non-roster attendees</span>
            </div>
          )}

          {/* Note */}
          <div className="space-y-1">
            <Label className="text-xs">Note</Label>
            <Textarea
              value={draft.comment}
              onChange={(e) => setLocal({ comment: e.target.value })}
              onBlur={() => commitField("comment")}
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
