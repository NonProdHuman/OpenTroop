"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { Users } from "lucide-react"
import { DataTable } from "@/components/data-table"
import type { Member } from "@/types/api"

interface MembersTableProps {
  data: Member[]
  columns: ColumnDef<Member>[]
  isLoading: boolean
  onRowClick: (member: Member) => void
}

export function MembersTable({ data, columns, isLoading, onRowClick }: MembersTableProps) {
  return (
    <DataTable
      data={data}
      columns={columns}
      isLoading={isLoading}
      onRowClick={onRowClick}
      initialSorting={[{ id: "name", desc: false }]}
      emptyState={
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <div className="rounded-full bg-muted p-4">
            <Users className="h-7 w-7 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <p className="font-medium text-sm">No members match your filters.</p>
            <p className="text-xs text-muted-foreground">
              Try adjusting the search or filter options.
            </p>
          </div>
        </div>
      }
    />
  )
}
