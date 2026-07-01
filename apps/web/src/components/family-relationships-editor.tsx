"use client"

import { useState } from "react"
import { X, ChevronsUpDown } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useCreateRelationship, useDeleteRelationship } from "@/hooks/use-relationships"
import type { Member, MemberRelationship, RelationshipType } from "@/types/api"

const RELATIONSHIP_LABELS: Record<RelationshipType, string> = {
  parent_of: "Parent / guardian of",
  guardian_of: "Legal guardian of",
  sibling_of: "Sibling of",
  other: "Other",
}

function memberDisplayName(member: Member) {
  return `${member.first_name} ${member.last_name}`
}

function relLabel(rel: MemberRelationship, memberId: string): string {
  const type = rel.relationship_type
  if (rel.from_member_id === memberId) {
    return RELATIONSHIP_LABELS[type]
  }
  // Incoming edge — flip the label for display
  if (type === "parent_of") return "Child of"
  if (type === "guardian_of") return "Ward of"
  return RELATIONSHIP_LABELS[type]
}

function RelationshipBadge({
  rel,
  memberId,
  otherMember,
}: {
  rel: MemberRelationship
  memberId: string
  otherMember: Member | undefined
}) {
  const deleteRel = useDeleteRelationship()
  const label = relLabel(rel, memberId)
  const name = otherMember
    ? memberDisplayName(otherMember)
    : "(unknown member)"

  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border border-border bg-muted/40">
      <span className="text-muted-foreground">{label}:</span>
      <span>{name}</span>
      <button
        type="button"
        disabled={deleteRel.isPending}
        onClick={() => deleteRel.mutate({ relId: rel.id, memberId })}
        className="ml-0.5 rounded-full hover:opacity-70 disabled:opacity-40"
        aria-label={`Remove relationship with ${name}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}

interface FamilyRelationshipsEditorProps {
  memberId: string
  relationships: MemberRelationship[]
  allMembers: Member[]
}

export function FamilyRelationshipsEditor({
  memberId,
  relationships,
  allMembers,
}: FamilyRelationshipsEditorProps) {
  const [open, setOpen] = useState(false)
  const [selectedType, setSelectedType] = useState<RelationshipType>("parent_of")
  const createRel = useCreateRelationship()

  const memberById = new Map(allMembers.map((m) => [m.id, m]))

  // Members already in any relationship with this one (both directions)
  const linkedIds = new Set(
    relationships.flatMap((r) => [r.from_member_id, r.to_member_id]),
  )
  linkedIds.add(memberId)

  const available = allMembers.filter((m) => !linkedIds.has(m.id) && !m.is_deleted)

  function handleAdd(other: Member) {
    // Directional convention: for sibling_of, store lower-UUID as from_member.
    const isSymmetric = selectedType === "sibling_of" || selectedType === "other"
    const [from, to] =
      isSymmetric && memberId > other.id
        ? [other.id, memberId]
        : [memberId, other.id]
    createRel.mutate({ from_member_id: from, to_member_id: to, relationship_type: selectedType })
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {relationships.length === 0 && (
          <span className="text-sm text-muted-foreground">No family relationships</span>
        )}
        {relationships.map((rel) => {
          const otherId =
            rel.from_member_id === memberId ? rel.to_member_id : rel.from_member_id
          return (
            <RelationshipBadge
              key={rel.id}
              rel={rel}
              memberId={memberId}
              otherMember={memberById.get(otherId)}
            />
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        <Select
          value={selectedType}
          onValueChange={(v) => setSelectedType(v as RelationshipType)}
        >
          <SelectTrigger className="h-7 text-xs w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="parent_of">Parent / guardian of</SelectItem>
            <SelectItem value="guardian_of">Legal guardian of</SelectItem>
            <SelectItem value="sibling_of">Sibling of</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>

        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            role="combobox"
            aria-expanded={open}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "h-7 gap-1.5 text-xs",
            )}
          >
            <ChevronsUpDown className="h-3 w-3" />
            Add member…
          </PopoverTrigger>
          <PopoverContent className="w-64 p-0" align="start">
            <Command>
              <CommandInput placeholder="Search members…" className="h-8" />
              <CommandList>
                <CommandEmpty>
                  {available.length === 0
                    ? "All members are already linked."
                    : "No members found."}
                </CommandEmpty>
                <CommandGroup>
                  {available.map((m) => (
                    <CommandItem
                      key={m.id}
                      value={memberDisplayName(m)}
                      onSelect={() => handleAdd(m)}
                      className="gap-2"
                    >
                      <span>{memberDisplayName(m)}</span>
                      <span className="ml-auto text-xs text-muted-foreground capitalize">
                        {m.member_type}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  )
}
