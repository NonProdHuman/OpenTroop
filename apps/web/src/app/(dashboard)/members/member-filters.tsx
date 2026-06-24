"use client"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Search, X } from "lucide-react"
import type { MemberStatus, MemberType } from "@/types/api"
import { cn } from "@/lib/utils"

const TYPE_OPTIONS: { value: MemberType; label: string }[] = [
  { value: "scout", label: "Scouts" },
  { value: "adult", label: "Adults" },
]

const STATUS_OPTIONS: { value: MemberStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "alumni", label: "Alumni" },
]

interface MemberFiltersProps {
  search: string
  types: MemberType[]
  statuses: MemberStatus[]
  onSearchChange: (v: string) => void
  onTypeToggle: (v: MemberType) => void
  onStatusToggle: (v: MemberStatus) => void
  onClear: () => void
}

export function MemberFilters({
  search,
  types,
  statuses,
  onSearchChange,
  onTypeToggle,
  onStatusToggle,
  onClear,
}: MemberFiltersProps) {
  const isDirty = search !== "" || types.length > 0 || statuses.length > 0

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-wrap">
      <div className="relative flex-1 min-w-48">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          placeholder="Search members…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="flex items-center gap-1">
        {TYPE_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={types.includes(opt.value) ? "default" : "outline"}
            size="sm"
            onClick={() => onTypeToggle(opt.value)}
            className={cn("h-8")}
          >
            {opt.label}
          </Button>
        ))}
      </div>

      <div className="flex items-center gap-1">
        {STATUS_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={statuses.includes(opt.value) ? "default" : "outline"}
            size="sm"
            onClick={() => onStatusToggle(opt.value)}
          >
            {opt.label}
          </Button>
        ))}
      </div>

      {isDirty && (
        <Button variant="ghost" size="sm" onClick={onClear} className="h-8 px-2">
          <X className="h-4 w-4 mr-1" />
          Clear
        </Button>
      )}
    </div>
  )
}
