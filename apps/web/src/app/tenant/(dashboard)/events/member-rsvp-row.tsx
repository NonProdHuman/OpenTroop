"use client"

import { useState } from "react"
import { AlertTriangle, Check, ChevronDown, ChevronUp } from "lucide-react"
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
import { isDirectGuardian } from "@/lib/household"
import { useGrantPermission } from "@/hooks/use-events"
import { useRsvpDraft } from "@/hooks/use-rsvp-draft"
import type {
  Event,
  EventParticipant,
  Member,
  MemberRelationship,
  RsvpStatus,
} from "@/types/api"
import { CheckboxButton, RsvpStatusButtons } from "./rsvp-controls"

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

/** One household member's self-service RSVP: status buttons, permission-slip
 * flow, and (expanded) driver/guest/note details. */
export function MemberRsvpRow({
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
  const [showPermDialog, setShowPermDialog] = useState(false)

  const { draft, setAndPersist, setLocal, commitField } = useRsvpDraft(
    event.id,
    member.id,
    participant,
    draftFrom,
  )

  const isScout = member.member_type === "scout"
  const needsSlip = event.event_type.require_permission_slip && isScout
  const slipStatus = participant?.permission_status
  const canSign = isDirectGuardian(actorId, member.id, relationships)
  const slipPending = needsSlip && slipStatus === "pending" && draft.rsvp_status === "going"

  function handleRsvpChange(s: RsvpStatus) {
    setAndPersist({ rsvp_status: s })
    if (s === "going" && needsSlip && canSign && slipStatus !== "granted") {
      setShowPermDialog(true)
    }
  }

  return (
    <div className="rounded-md border border-border p-3 space-y-2">
      {/* Top row: name + RSVP buttons */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {member.first_name} {member.last_name}
          </span>
          <span className="text-xs text-muted-foreground capitalize">{member.member_type}</span>
          {slipPending && (
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
        <PermissionSlipDialog
          member={member}
          eventId={event.id}
          permissionMessage={permissionMessage}
          open={showPermDialog}
          onOpenChange={setShowPermDialog}
        />
      )}

      {/* "Give permission" button shown to a guardian when slip is pending */}
      {!showPermDialog && slipPending && canSign && (
        <Button
          size="sm"
          className="h-8 text-xs bg-amber-600 hover:bg-amber-700 text-white"
          onClick={() => setShowPermDialog(true)}
        >
          <AlertTriangle className="h-3 w-3 mr-1" />
          Give permission for {member.first_name}
        </Button>
      )}

      {expanded && (
        <RsvpDetailFields
          member={member}
          event={event}
          draft={draft}
          setAndPersist={setAndPersist}
          setLocal={setLocal}
          commitField={commitField}
        />
      )}
    </div>
  )
}

/** The troop's permission language plus an electronic-signature input; granting
 * records the signature via the permission endpoint. */
function PermissionSlipDialog({
  member,
  eventId,
  permissionMessage,
  open,
  onOpenChange,
}: {
  member: Member
  eventId: string
  permissionMessage: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [sigInput, setSigInput] = useState("")
  const grantPermission = useGrantPermission(eventId)

  function handleGrantPermission() {
    if (!sigInput.trim()) return
    grantPermission.mutate(
      { memberId: member.id, signature: sigInput.trim() },
      {
        onSuccess: () => {
          onOpenChange(false)
          setSigInput("")
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
          <Button variant="outline" onClick={() => onOpenChange(false)}>
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
  )
}

/** Expanded detail: drivers, guests, note. */
function RsvpDetailFields({
  member,
  event,
  draft,
  setAndPersist,
  setLocal,
  commitField,
}: {
  member: Member
  event: Event
  draft: RsvpDraft
  setAndPersist: (changes: Partial<RsvpDraft>) => void
  setLocal: (changes: Partial<RsvpDraft>) => void
  commitField: (field: keyof RsvpDraft) => void
}) {
  return (
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
      {event.event_type.allow_guests && (
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
  )
}
