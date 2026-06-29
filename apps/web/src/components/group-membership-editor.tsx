"use client"

import { useState } from "react"
import { Shield, Users, Lock, X, ChevronsUpDown, Check } from "lucide-react"
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
import type { Group } from "@/types/api"
import { useAddGroupMember, useRemoveGroupMember } from "@/hooks/use-groups"
import { cn } from "@/lib/utils"

// Fallback accent colors when group.color is null
const TYPE_FALLBACK: Record<string, string> = {
  patrol: "#F59E0B",  // amber
  custom: "#3B82F6",  // blue
}
const SYSTEM_COLOR = "#6B7280" // gray

function accentColor(group: Group): string {
  if (group.color) return group.color
  if (group.is_system) return SYSTEM_COLOR
  return TYPE_FALLBACK[group.group_type] ?? "#6B7280"
}

function isRemovable(group: Group): boolean {
  return !group.is_system
}

function GroupTypeIcon({ group, className }: { group: Group; className?: string }) {
  const cls = cn("h-3 w-3 shrink-0", className)
  if (group.is_system) return <Lock className={cls} />
  switch (group.group_type) {
    case "patrol":  return <Shield className={cls} />
    default:        return <Users className={cls} />
  }
}

function GroupBubble({
  group,
  memberId,
  onRemoved,
}: {
  group: Group
  memberId: string
  onRemoved?: () => void
}) {
  const removeGroupMember = useRemoveGroupMember()
  const color = accentColor(group)
  const removable = isRemovable(group)

  function handleRemove() {
    removeGroupMember.mutate(
      { groupId: group.id, memberId },
      { onSuccess: onRemoved },
    )
  }

  return (
    <span
      title={
        group.is_system
          ? "System group — membership is managed automatically"
          : undefined
      }
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
        "border transition-opacity",
        !removable && "opacity-75",
      )}
      style={{
        borderColor: color,
        color,
        backgroundColor: `${color}18`, // ~10% opacity fill
      }}
    >
      <GroupTypeIcon group={group} />
      {group.name}
      {removable && (
        <button
          type="button"
          onClick={handleRemove}
          disabled={removeGroupMember.isPending}
          className="ml-0.5 rounded-full hover:opacity-70 disabled:opacity-40"
          aria-label={`Remove from ${group.name}`}
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  )
}

interface GroupMembershipEditorProps {
  memberId: string
  /** Groups this member currently belongs to (resolved). */
  memberGroups: Group[]
  /** All groups in the tenant. */
  allGroups: Group[]
}

export function GroupMembershipEditor({
  memberId,
  memberGroups,
  allGroups,
}: GroupMembershipEditorProps) {
  const [open, setOpen] = useState(false)
  const addGroupMember = useAddGroupMember()

  const memberGroupIds = new Set(memberGroups.map((g) => g.id))

  // Groups available to add: exclude current memberships and system groups.
  // Custom groups accept manual members even when they also have rules.
  const addable = allGroups.filter(
    (g) => !memberGroupIds.has(g.id) && !g.is_system,
  )

  function handleAdd(group: Group) {
    addGroupMember.mutate({ groupId: group.id, memberId })
    setOpen(false)
  }

  // Sort: patrols first, then alphabetical within type
  const sorted = [...memberGroups].sort((a, b) => {
    if (a.group_type === "patrol" && b.group_type !== "patrol") return -1
    if (a.group_type !== "patrol" && b.group_type === "patrol") return 1
    return a.name.localeCompare(b.name)
  })

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {sorted.length === 0 && (
          <span className="text-sm text-muted-foreground">No group memberships</span>
        )}
        {sorted.map((group) => (
          <GroupBubble key={group.id} group={group} memberId={memberId} />
        ))}
      </div>

      {allGroups.filter((g) => !g.is_system).length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No groups have been created yet.{" "}
          <a href="/groups" className="underline underline-offset-2">
            Create groups
          </a>{" "}
          first, then assign members here.
        </p>
      ) : (
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            role="combobox"
            aria-expanded={open}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 gap-1.5 text-xs")}
          >
            <ChevronsUpDown className="h-3 w-3" />
            Add to group…
          </PopoverTrigger>
          <PopoverContent className="w-64 p-0" align="start">
            <Command>
              <CommandInput placeholder="Search groups…" className="h-8" />
              <CommandList>
                <CommandEmpty>
                  {addable.length === 0
                    ? "Member is already in all available groups."
                    : "No groups found."}
                </CommandEmpty>
                <CommandGroup>
                  {addable.map((group) => (
                    <CommandItem
                      key={group.id}
                      value={group.name}
                      onSelect={() => handleAdd(group)}
                      className="gap-2"
                    >
                      <GroupTypeIcon
                        group={group}
                        className="text-muted-foreground"
                      />
                      <span>{group.name}</span>
                      <span className="ml-auto text-xs text-muted-foreground capitalize">
                        {group.group_type}
                      </span>
                      <Check className="h-3.5 w-3.5 opacity-0" />
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}
    </div>
  )
}
