"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { Calendar } from "lucide-react"
import { DataTable } from "@/components/data-table"
import type { Event } from "@/types/api"

interface EventsTableProps {
  data: Event[]
  columns: ColumnDef<Event>[]
  isLoading: boolean
  onRowClick: (event: Event) => void
}

export function EventsTable({ data, columns, isLoading, onRowClick }: EventsTableProps) {
  return (
    <DataTable
      data={data}
      columns={columns}
      isLoading={isLoading}
      onRowClick={onRowClick}
      initialSorting={[{ id: "when", desc: false }]}
      emptyState={
        <div className="flex flex-col items-center justify-center gap-3 py-20 text-muted-foreground">
          <Calendar className="h-10 w-10 opacity-40" />
          <p className="text-sm">No events match your filters.</p>
        </div>
      }
    />
  )
}
