"use client"

import { useMemo, useState } from "react"
import { formatMemberName } from "@/lib/format"
import { Users } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useMembers } from "@/hooks/use-members"
import { useGroupMemberships, usePatrolMemberships } from "@/hooks/use-groups"
import { useEventAudiences, useEventParticipants } from "@/hooks/use-events"
import { useRsvpDraft } from "@/hooks/use-rsvp-draft"
import type { Event, EventParticipant, Member, RsvpStatus } from "@/types/api"
import { CheckboxButton, RsvpStatusButtons } from "../../rsvp-controls"

const memberName = formatMemberName

// ---------------------------------------------------------------------------
// Local editable state for one member's RSVP (leader-managed subset)
// ---------------------------------------------------------------------------

type RsvpDraft = {
  rsvp_status: RsvpStatus
  driver: boolean
  seat_count: number | null
  comment: string
}

function draftFrom(participant: EventParticipant | undefined): RsvpDraft {
  return {
    rsvp_status: participant?.rsvp_status ?? "no_response",
    driver: participant?.driver ?? false,
    seat_count: participant?.seat_count ?? null,
    comment: participant?.comment ?? "",
  }
}

function MemberRsvpAdminRow({
  member,
  event,
  participant,
  patrolName,
}: {
  member: Member
  event: Event
  participant: EventParticipant | undefined
  patrolName?: string
}) {
  const { draft, setAndPersist, setLocal, commitField } = useRsvpDraft(
    event.id,
    member.id,
    participant,
    draftFrom,
  )

  const isAdult = member.member_type === "adult"

  return (
    <div className="rounded-md border border-border p-3 space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{memberName(member)}</span>
          <span className="text-xs text-muted-foreground capitalize">{member.member_type}</span>
          {patrolName && (
            <span className="text-xs text-muted-foreground">· {patrolName}</span>
          )}
        </div>
        <RsvpStatusButtons
          value={draft.rsvp_status}
          onChange={(s) => setAndPersist({ rsvp_status: s })}
          labels={{ no_response: "Clear" }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-1">
        {isAdult && (
          <div className="flex items-center gap-2">
            <CheckboxButton
              checked={draft.driver}
              onToggle={() => setAndPersist({ driver: !draft.driver })}
              label="Driver"
            />
            <Label className="text-xs cursor-pointer">Driver</Label>
            {draft.driver && (
              <div className="flex items-center gap-1.5 pl-1">
                <Label className="text-xs">Seatbelts</Label>
                <Input
                  type="number"
                  min={1}
                  max={15}
                  value={draft.seat_count ?? ""}
                  onChange={(e) =>
                    setLocal({ seat_count: e.target.value ? Number(e.target.value) : null })
                  }
                  onBlur={() => commitField("seat_count")}
                  className="h-7 w-16 text-sm"
                />
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-1.5 flex-1 min-w-[12rem]">
          <Label className="text-xs shrink-0">Comment</Label>
          <Input
            value={draft.comment}
            onChange={(e) => setLocal({ comment: e.target.value })}
            onBlur={() => commitField("comment")}
            placeholder="Note…"
            className="h-7 text-sm"
          />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main admin panel
// ---------------------------------------------------------------------------

type TypeFilter = "all" | "scout" | "adult"
type SortKey = "name" | "patrol" | "rsvp"

// Order RSVP statuses for sorting: confirmed first, declined last.
const RSVP_ORDER: Record<RsvpStatus, number> = {
  going: 0,
  maybe: 1,
  no_response: 2,
  declined: 3,
}

const TYPE_FILTERS: { value: TypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scout", label: "Scouts" },
  { value: "adult", label: "Adults" },
]

export function EventRsvpAdmin({ event }: { event: Event }) {
  const [search, setSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all")
  const [driversOnly, setDriversOnly] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>("name")

  const { data: allMembers = [] } = useMembers()
  const { data: audiences = [] } = useEventAudiences(event.id)
  const { data: participants = [] } = useEventParticipants(event.id)
  const groupsByMember = useGroupMemberships()
  const patrolByMember = usePatrolMemberships()

  const participantByMemberId = useMemo(
    () => new Map(participants.map((p) => [p.member_id, p])),
    [participants],
  )

  // Audience-scoped roster: empty audiences ⇒ all active members; otherwise the
  // union of members resolving into any audience group. Active-only by design.
  const roster = useMemo(() => {
    const audienceGroupIds = new Set(audiences.map((a) => a.group_id))
    const active = allMembers.filter(
      (m) => !m.is_deleted && m.membership_status === "active",
    )
    if (audienceGroupIds.size === 0) return active
    return active.filter((m) =>
      (groupsByMember.get(m.id) ?? []).some((g) => audienceGroupIds.has(g.id)),
    )
  }, [audiences, allMembers, groupsByMember])

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase()
    const result = roster.filter((m) => {
      if (typeFilter !== "all" && m.member_type !== typeFilter) return false
      if (driversOnly && !participantByMemberId.get(m.id)?.driver) return false
      if (q && !memberName(m).toLowerCase().includes(q)) return false
      return true
    })
    const patrolName = (m: Member) => patrolByMember.get(m.id)?.name ?? ""
    const rsvpRank = (m: Member) =>
      RSVP_ORDER[participantByMemberId.get(m.id)?.rsvp_status ?? "no_response"]
    return [...result].sort((a, b) => {
      if (sortKey === "patrol") {
        const cmp = patrolName(a).localeCompare(patrolName(b))
        if (cmp !== 0) return cmp
      } else if (sortKey === "rsvp") {
        const cmp = rsvpRank(a) - rsvpRank(b)
        if (cmp !== 0) return cmp
      }
      return memberName(a).localeCompare(memberName(b))
    })
  }, [roster, search, typeFilter, driversOnly, sortKey, participantByMemberId, patrolByMember])

  const goingCount = participants.filter((p) => p.rsvp_status === "going").length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          {audiences.length === 0
            ? "All active members can see this event."
            : "Members in this event's audience groups."}
        </p>
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <Users className="h-3.5 w-3.5" />
          {goingCount} going
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search members…"
          className="h-8 max-w-[12rem]"
        />

        {/* Member-type filter */}
        <div className="flex gap-1">
          {TYPE_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => setTypeFilter(value)}
              className={cn(
                "text-xs px-2 py-1 rounded-md border transition-colors",
                typeFilter === value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Drivers-only filter */}
        <button
          type="button"
          aria-pressed={driversOnly}
          onClick={() => setDriversOnly((v) => !v)}
          className={cn(
            "text-xs px-2 py-1 rounded-md border transition-colors",
            driversOnly
              ? "bg-primary text-primary-foreground border-primary"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          Drivers
        </button>

        {/* Sort */}
        <div className="flex items-center gap-1.5 ml-auto">
          <Label className="text-xs text-muted-foreground shrink-0">Sort</Label>
          <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
            <SelectTrigger className="h-8 w-[7.5rem]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="name">Name</SelectItem>
              <SelectItem value="patrol">Patrol</SelectItem>
              <SelectItem value="rsvp">RSVP</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">No members match.</p>
      ) : (
        <div className="space-y-2">
          {visible.map((m) => (
            <MemberRsvpAdminRow
              key={m.id}
              member={m}
              event={event}
              participant={participantByMemberId.get(m.id)}
              patrolName={patrolByMember.get(m.id)?.name}
            />
          ))}
        </div>
      )}
    </div>
  )
}
