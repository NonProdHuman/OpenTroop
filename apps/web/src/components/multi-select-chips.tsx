"use client"

import { useState } from "react"
import { Check, Plus, X } from "lucide-react"
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
import { cn } from "@/lib/utils"

export interface ChipOption {
  id: string
  label: string
  /** Optional short qualifier shown muted after the label (e.g. "Youth", "Adult"). */
  badge?: string
}

interface MultiSelectChipsProps {
  /** All selectable options. */
  options: ChipOption[]
  /** Currently selected option IDs. */
  selectedIds: string[]
  /** Called with the next selection whenever an item is toggled or a chip removed. */
  onChange: (nextIds: string[]) => void
  /** Trigger button copy, e.g. "Add position…". */
  addLabel: string
  /** Search box placeholder. */
  searchPlaceholder?: string
  /** Empty-state copy when the search matches nothing. */
  emptyLabel?: string
  /** Optional prefix for each chip's label, e.g. "Parents of: ". */
  chipPrefix?: string
}

/**
 * A chip-based multi-select: selected values render as removable bubbles, and an
 * "Add…" popover holds a searchable list. Selecting an item toggles it **without
 * closing the popover**, so several values can be added in a row. The chips stay
 * visible alongside the open picker.
 */
export function MultiSelectChips({
  options,
  selectedIds,
  onChange,
  addLabel,
  searchPlaceholder = "Search…",
  emptyLabel = "No matches.",
  chipPrefix = "",
}: MultiSelectChipsProps) {
  const [open, setOpen] = useState(false)
  const selected = new Set(selectedIds)
  const optionById = new Map(options.map((o) => [o.id, o]))

  function toggle(id: string) {
    onChange(selected.has(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id])
  }

  return (
    <div className="space-y-2">
      {selectedIds.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedIds.map((id) => {
            const opt = optionById.get(id)
            return (
              <Badge key={id} variant="secondary" className="text-xs gap-1 py-0.5">
                {chipPrefix}
                {opt?.label ?? id}
                {opt?.badge && (
                  <span className="text-[10px] font-normal text-muted-foreground">{opt.badge}</span>
                )}
                <button
                  type="button"
                  onClick={() => toggle(id)}
                  aria-label={`Remove ${opt?.label ?? id}`}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )
          })}
        </div>
      )}

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-6 text-xs gap-1")}
          aria-expanded={open}
        >
          <Plus className="h-3 w-3" /> {addLabel}
        </PopoverTrigger>
        <PopoverContent className="w-56 p-0" align="start">
          <Command>
            <CommandInput placeholder={searchPlaceholder} className="h-8" />
            <CommandList>
              <CommandEmpty>{emptyLabel}</CommandEmpty>
              <CommandGroup>
                {options.map((o) => {
                  const isSelected = selected.has(o.id)
                  return (
                    <CommandItem
                      key={o.id}
                      value={o.label}
                      // Keep the popover open so multiple values can be picked.
                      onSelect={() => toggle(o.id)}
                      className="gap-2"
                    >
                      <Check className={cn("h-3.5 w-3.5", isSelected ? "opacity-100" : "opacity-0")} />
                      <span>{o.label}</span>
                      {o.badge && (
                        <span className="ml-auto text-xs text-muted-foreground">{o.badge}</span>
                      )}
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  )
}
