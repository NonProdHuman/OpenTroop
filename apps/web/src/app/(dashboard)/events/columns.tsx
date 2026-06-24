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
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
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
          <span className="text-muted-foreground whitespace-nowrap">
            {formatEventWhen(e.scheduled_start, e.scheduled_end, e.all_day)}
          </span>
        )
      },
    },
    {
      id: "location",
      accessorFn: (row) => row.location?.name ?? row.location_notes ?? "",
      header: "Location",
      cell: ({ row }) => {
        const e = row.original
        const where = e.location?.name ?? e.location_notes
        return <span className="text-muted-foreground">{where ?? "—"}</span>
      },
    },
  ]
}
