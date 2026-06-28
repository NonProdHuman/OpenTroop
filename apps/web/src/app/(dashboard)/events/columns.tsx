"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { ArrowUpDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { formatEventWhen } from "@/lib/format"
import type { Event } from "@/types/api"
import { EventTypeBadge } from "./event-type-badge"

export function buildColumns(): ColumnDef<Event>[] {
  return [
    {
      id: "name",
      accessorKey: "name",
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          className="-ml-3"
        >
          Event
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => (
        <div
          className="font-medium max-w-[100px] sm:max-w-[150px] md:max-w-[200px] lg:max-w-[250px] truncate"
          title={row.original.name}
        >
          {row.original.name}
        </div>
      ),
    },
    {
      id: "type",
      accessorFn: (row) => row.event_type.name,
      header: "Type",
      cell: ({ row }) => <EventTypeBadge type={row.original.event_type} />,
    },
    {
      id: "when",
      accessorFn: (row) => row.scheduled_start,
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          className="-ml-3"
        >
          When
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const e = row.original
        return (
          <div className="text-muted-foreground max-w-[120px] sm:max-w-[160px] md:max-w-none">
            {formatEventWhen(e.scheduled_start, e.scheduled_end, e.all_day, true)}
          </div>
        )
      },
    },
    {
      id: "location",
      accessorFn: (row) => row.location?.name ?? row.location_notes ?? "",
      header: "Location",
      meta: {
        className: "hidden md:table-cell",
      },
      cell: ({ row }) => {
        const e = row.original
        const where = e.location?.name ?? e.location_notes
        return (
          <div
            className="max-w-[100px] md:max-w-[150px] lg:max-w-[200px] truncate text-muted-foreground"
            title={where ?? undefined}
          >
            {where ?? "—"}
          </div>
        )
      },
    },
  ]
}
