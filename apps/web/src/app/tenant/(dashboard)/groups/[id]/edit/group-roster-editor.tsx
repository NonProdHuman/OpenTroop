"use client"

import { useState } from "react"
import { X } from "lucide-react"
import { SectionTitle } from "@/components/form-helpers"
import { buttonVariants } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { useAddGroupMember, useRemoveGroupMember } from "@/hooks/use-groups"
import type { Group, GroupType, Member } from "@/types/api"

function displayName(m: { first_name: string; last_name: string; nickname: string | null }) {
  return m.nickname ? `${m.first_name} "${m.nickname}" ${m.last_name}` : `${m.first_name} ${m.last_name}`
}

// Manual (hand-added, removable) and rule-derived (display-only) member lists
// for the group edit page.
export function GroupRosterEditor({
  group,
  type,
  members,
  manualMemberIds,
  allMembers,
}: {
  group: Group
  type: GroupType
  members: Member[]
  manualMemberIds: Set<string>
  allMembers: Member[]
}) {
  const addMember = useAddGroupMember()
  const removeMember = useRemoveGroupMember()
  const [addMemberOpen, setAddMemberOpen] = useState(false)

  const isSystem = group.is_system

  // Split the resolved set into hand-added (removable) vs rule-derived (display only).
  const manualMembers = members.filter((m) => manualMemberIds.has(m.id))
  const dynamicMembers = members.filter((m) => !manualMemberIds.has(m.id))
  const dynamicIds = new Set(dynamicMembers.map((m) => m.id))

  // Exclude only existing *manual* members — a rule-matched member can still be
  // added to "pin" them so they stay even if the rule later stops matching.
  const addableMembers = allMembers.filter((m) => {
    if (m.is_deleted) return false
    if (manualMemberIds.has(m.id)) return false
    if (type === "patrol" && m.member_type === "adult") return false
    return true
  })

  return (
    <>
      <SectionTitle>Members{manualMembers.length > 0 ? ` (${manualMembers.length})` : ""}</SectionTitle>
      <div className="space-y-2">
        {manualMembers.length === 0 ? (
          <p className="text-sm text-muted-foreground">No members added by hand.</p>
        ) : (
          <ul className="divide-y rounded-md border max-h-60 overflow-y-auto">
            {manualMembers.map((m) => (
              <li key={m.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span>{displayName(m)}</span>
                {!isSystem && (
                  <button
                    type="button"
                    onClick={() => removeMember.mutate({ groupId: group.id, memberId: m.id })}
                    disabled={removeMember.isPending}
                    className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                    aria-label={`Remove ${displayName(m)}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {!isSystem && (
          <Popover open={addMemberOpen} onOpenChange={setAddMemberOpen}>
            <PopoverTrigger
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 text-xs gap-1")}
              aria-expanded={addMemberOpen}
            >
              Add member…
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0" align="start">
              <Command>
                <CommandInput placeholder="Search members…" className="h-8" />
                <CommandList>
                  <CommandEmpty>
                    {addableMembers.length === 0
                      ? "All members are already in this group."
                      : "No members found."}
                  </CommandEmpty>
                  <CommandGroup>
                    {addableMembers.map((m) => (
                      <CommandItem
                        key={m.id}
                        value={displayName(m)}
                        onSelect={() => {
                          addMember.mutate({ groupId: group.id, memberId: m.id })
                          setAddMemberOpen(false)
                        }}
                      >
                        {displayName(m)}
                        {dynamicIds.has(m.id) && (
                          <span className="ml-auto text-xs text-muted-foreground italic">
                            via rules — pin
                          </span>
                        )}
                        <span className={cn("text-xs text-muted-foreground capitalize", !dynamicIds.has(m.id) && "ml-auto")}>
                          {m.member_type}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        )}
      </div>

      {/* ── Rule-derived members (display only) ───────────── */}
      {dynamicMembers.length > 0 && (
        <div className="space-y-2">
          <SectionTitle>From Rules ({dynamicMembers.length})</SectionTitle>
          <ul className="divide-y rounded-md border max-h-60 overflow-y-auto bg-muted/20">
            {dynamicMembers.map((m) => (
              <li
                key={m.id}
                className="flex items-center justify-between px-3 py-2 text-sm text-muted-foreground"
              >
                <span>{displayName(m)}</span>
                <span className="text-xs italic">{group.include_parents && m.member_type === "adult" ? "rule / parent" : "via rules"}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground italic">
            Resolved automatically from the rules below — adjust the rules to change who&apos;s included.
          </p>
        </div>
      )}
    </>
  )
}
