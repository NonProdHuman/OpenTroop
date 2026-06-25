"use client"

import { type ColumnDef } from "@tanstack/react-table"
import type { Member } from "@/types/api"
import type { PatrolInfo } from "@/hooks/use-groups"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowUpDown } from "lucide-react"

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
  patrolMap: Map<string, PatrolInfo>,
  roleMap: Map<string, string>,
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
      id: "patrol",
      header: "Patrol",
      cell: ({ row }) => {
        const patrol = patrolMap.get(row.original.id)
        return patrol ? (
          <span>{patrol.name}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )
      },
    },
    {
      id: "role",
      header: "Role",
      cell: ({ row }) => {
        const role = roleMap.get(row.original.id)
        return role ? (
          <span className="text-sm">{role}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )
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
        if (val === "active") return null
        return (
          <Badge variant={STATUS_VARIANTS[val] ?? "outline"}>
            {val.charAt(0).toUpperCase() + val.slice(1)}
          </Badge>
        )
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
