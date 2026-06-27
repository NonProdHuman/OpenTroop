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
import type { MemberPositionAssignment, Position } from "@/types/api"
import { useAssignMemberPosition, useRemoveMemberPosition } from "@/hooks/use-member-positions"
import { cn } from "@/lib/utils"

function PositionBadge({
  assignment,
  position,
  memberId,
  canAssign,
}: {
  assignment: MemberPositionAssignment
  position: Position
  memberId: string
  canAssign: boolean
}) {
  const removePosition = useRemoveMemberPosition()
  const removable = canAssign && !position.is_system

  return (
    <span
      title={position.is_system ? "System position — managed by OpenTroop" : undefined}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
        "border border-border bg-muted text-foreground transition-opacity",
        !removable && "opacity-75",
      )}
    >
      {position.name}
      {removable && (
        <button
          type="button"
          onClick={() => removePosition.mutate({ memberId, positionId: position.id })}
          disabled={removePosition.isPending}
          className="ml-0.5 rounded-full hover:opacity-70 disabled:opacity-40"
          aria-label={`Remove ${position.name}`}
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  )
}

interface MemberPositionsEditorProps {
  memberId: string
  /** Current position assignments for this member. */
  assignments: MemberPositionAssignment[]
  /** All positions in the tenant. */
  allPositions: Position[]
  /** Whether the caller holds role:assign. */
  canAssign: boolean
}

export function MemberPositionsEditor({
  memberId,
  assignments,
  allPositions,
  canAssign,
}: MemberPositionsEditorProps) {
  const [open, setOpen] = useState(false)
  const assignPosition = useAssignMemberPosition()

  const assignedIds = new Set(assignments.map((a) => a.position_id))

  // Sort by position sort_order then name
  const sorted = [...assignments].sort((a, b) => {
    const pa = allPositions.find((p) => p.id === a.position_id)
    const pb = allPositions.find((p) => p.id === b.position_id)
    if (!pa || !pb) return 0
    if (pa.sort_order !== pb.sort_order) return pa.sort_order - pb.sort_order
    return pa.name.localeCompare(pb.name)
  })

  const addable = allPositions.filter((p) => !assignedIds.has(p.id))

  function handleAdd(position: Position) {
    assignPosition.mutate({ memberId, positionId: position.id })
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5 min-h-[2rem] items-center">
        {sorted.length === 0 && (
          <span className="text-sm text-muted-foreground">No positions assigned</span>
        )}
        {sorted.map((a) => {
          const position = allPositions.find((p) => p.id === a.position_id)
          if (!position) return null
          return (
            <PositionBadge
              key={a.id}
              assignment={a}
              position={position}
              memberId={memberId}
              canAssign={canAssign}
            />
          )
        })}
      </div>

      {canAssign && (
        allPositions.length === 0 ? (
          <p className="text-xs text-muted-foreground">No positions have been created yet.</p>
        ) : (
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger
              role="combobox"
              aria-expanded={open}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 gap-1.5 text-xs")}
            >
              <ChevronsUpDown className="h-3 w-3" />
              Add position…
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0" align="start">
              <Command>
                <CommandInput placeholder="Search positions…" className="h-8" />
                <CommandList>
                  <CommandEmpty>
                    {addable.length === 0
                      ? "All positions are already assigned."
                      : "No positions found."}
                  </CommandEmpty>
                  <CommandGroup>
                    {addable.map((position) => (
                      <CommandItem
                        key={position.id}
                        value={position.name}
                        onSelect={() => handleAdd(position)}
                        className="gap-2"
                      >
                        <span>{position.name}</span>
                        <span className="ml-auto text-xs text-muted-foreground capitalize">
                          {position.applies_to}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        )
      )}
    </div>
  )
}
