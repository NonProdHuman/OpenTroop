"use client"

import { Search, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { EventType } from "@/types/api"

export type TimeFilter = "upcoming" | "past" | "all"

const TIME_OPTIONS: { value: TimeFilter; label: string }[] = [
  { value: "upcoming", label: "Upcoming" },
  { value: "past", label: "Past" },
  { value: "all", label: "All" },
]

interface EventFiltersProps {
  search: string
  timeFilter: TimeFilter
  typeIds: string[]
  eventTypes: EventType[]
  onSearchChange: (v: string) => void
  onTimeChange: (v: TimeFilter) => void
  onTypeToggle: (id: string) => void
  onClear: () => void
}

export function EventFilters({
  search,
  timeFilter,
  typeIds,
  eventTypes,
  onSearchChange,
  onTimeChange,
  onTypeToggle,
  onClear,
}: EventFiltersProps) {
  const isDirty = search !== "" || timeFilter !== "upcoming" || typeIds.length > 0

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="relative min-w-48 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search events…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="flex items-center gap-1">
        {TIME_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={timeFilter === opt.value ? "default" : "outline"}
            size="sm"
            onClick={() => onTimeChange(opt.value)}
            className="h-8"
          >
            {opt.label}
          </Button>
        ))}
      </div>

      {eventTypes.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1">
          {eventTypes.map((t) => (
            <Button
              key={t.id}
              variant={typeIds.includes(t.id) ? "default" : "outline"}
              size="sm"
              onClick={() => onTypeToggle(t.id)}
              className="h-8"
            >
              {t.name}
            </Button>
          ))}
        </div>
      ) : null}

      {isDirty ? (
        <Button variant="ghost" size="sm" onClick={onClear} className={cn("h-8 px-2")}>
          <X className="mr-1 h-4 w-4" />
          Clear
        </Button>
      ) : null}
    </div>
  )
}
