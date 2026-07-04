"use client"

import { useState } from "react"
import { ChevronsUpDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatMemberName } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { AdvancementScout } from "@/types/api"

export const NO_PATROL_LABEL = "No patrol"

/**
 * Group picker rows by patrol: patrols alphabetically, patrol-less scouts in a
 * trailing "No patrol" group. Scouts keep the API's last-name ordering within
 * each group.
 */
export function groupScoutsByPatrol(
  scouts: AdvancementScout[],
): { patrol: string; scouts: AdvancementScout[] }[] {
  const byPatrol = new Map<string, AdvancementScout[]>()
  for (const scout of scouts) {
    const key = scout.patrol_name ?? NO_PATROL_LABEL
    const group = byPatrol.get(key)
    if (group) group.push(scout)
    else byPatrol.set(key, [scout])
  }
  return [...byPatrol.entries()]
    .sort(([a], [b]) => {
      if (a === NO_PATROL_LABEL) return 1
      if (b === NO_PATROL_LABEL) return -1
      return a.localeCompare(b)
    })
    .map(([patrol, members]) => ({ patrol, scouts: members }))
}

export function ScoutPicker({
  scouts,
  selectedId,
  onSelect,
}: {
  scouts: AdvancementScout[]
  selectedId: string | null
  onSelect: (memberId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const selected = scouts.find((s) => s.member_id === selectedId) ?? null

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        role="combobox"
        aria-expanded={open}
        className={cn(buttonVariants({ variant: "outline" }), "w-72 justify-between")}
      >
        <span className="truncate">
          {selected ? formatMemberName(selected) : "Choose a scout…"}
        </span>
        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search scouts…" className="h-9" />
          <CommandList>
            <CommandEmpty>No scouts found.</CommandEmpty>
            {groupScoutsByPatrol(scouts).map((group) => (
              <CommandGroup key={group.patrol} heading={group.patrol}>
                {group.scouts.map((scout) => (
                  <CommandItem
                    key={scout.member_id}
                    value={`${formatMemberName(scout)} ${group.patrol}`}
                    onSelect={() => {
                      onSelect(scout.member_id)
                      setOpen(false)
                    }}
                  >
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate text-sm">
                        {formatMemberName(scout)}
                        {scout.membership_status !== "active" && (
                          <Badge variant="outline" className="ml-2 align-middle">
                            {scout.membership_status}
                          </Badge>
                        )}
                      </span>
                      <span className="text-muted-foreground truncate text-xs">
                        {scout.current_rank_name ?? "No rank yet"}
                      </span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
