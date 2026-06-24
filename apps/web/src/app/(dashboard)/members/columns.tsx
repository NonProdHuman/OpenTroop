"use client"

import { type ColumnDef } from "@tanstack/react-table"
import type { Member } from "@/types/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowUpDown } from "lucide-react"

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
  alumni: "Alumni",
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "outline"> = {
  active: "default",
  inactive: "secondary",
  alumni: "outline",
}

const TYPE_LABELS: Record<string, string> = {
  scout: "Scout",
  adult: "Adult",
}

export function buildColumns(
  patrolMap: Map<string, string>,
): ColumnDef<Member>[] {
  return [
    {
      id: "name",
      accessorFn: (row) => `${row.last_name} ${row.first_name}`,
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          className="-ml-3"
        >
          Name
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const m = row.original
        const display = m.nickname
          ? `${m.first_name} "${m.nickname}" ${m.last_name}`
          : `${m.first_name} ${m.last_name}`
        return <span className="font-medium">{display}</span>
      },
    },
    {
      id: "member_type",
      accessorKey: "member_type",
      header: "Type",
      cell: ({ getValue }) => {
        const val = getValue<string>()
        return (
          <Badge variant={val === "adult" ? "secondary" : "default"}>
            {TYPE_LABELS[val] ?? val}
          </Badge>
        )
      },
    },
    {
      id: "membership_status",
      accessorKey: "membership_status",
      header: "Status",
      cell: ({ getValue }) => {
        const val = getValue<string>()
        return (
          <Badge variant={STATUS_VARIANTS[val] ?? "outline"}>
            {STATUS_LABELS[val] ?? val}
          </Badge>
        )
      },
    },
    {
      id: "patrol",
      accessorFn: (row) => (row.patrol_id ? patrolMap.get(row.patrol_id) : ""),
      header: "Patrol",
      cell: ({ row }) => {
        const name = row.original.patrol_id
          ? patrolMap.get(row.original.patrol_id)
          : null
        return <span className="text-muted-foreground">{name ?? "—"}</span>
      },
    },
    {
      id: "email",
      accessorKey: "email",
      header: "Email",
      cell: ({ getValue }) => {
        const email = getValue<string | null>()
        return email ? (
          <a
            href={`mailto:${email}`}
            className="text-primary underline-offset-4 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {email}
          </a>
        ) : (
          <span className="text-muted-foreground">—</span>
        )
      },
    },
  ]
}
