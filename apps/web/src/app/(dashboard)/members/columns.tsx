"use client"

import { type ColumnDef } from "@tanstack/react-table"
import type { Member } from "@/types/api"
import type { PatrolInfo } from "@/hooks/use-groups"
 import { Button } from "@/components/ui/button"
import { ArrowUpDown } from "lucide-react"

const TYPE_LABELS: Record<string, string> = {
  scout: "Scout",
  adult: "Adult",
}

// Soft tinted badge classes — slate/amber palette
const TYPE_BADGE: Record<string, string> = {
  scout: "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300",
  adult: "bg-amber-50  text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300",
}

const STATUS_BADGE: Record<string, string> = {
  active:   "bg-green-50  text-green-700  border border-green-200  dark:bg-green-950  dark:text-green-300",
  inactive: "bg-slate-100 text-slate-500  border border-slate-200  dark:bg-slate-800  dark:text-slate-400",
  alumni:   "bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950 dark:text-purple-300",
}

function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
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
      header: () => <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Patrol</span>,
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
      header: () => <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Role</span>,
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
      header: () => <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Type</span>,
      cell: ({ getValue }) => {
        const val = getValue<string>()
        return (
          <TintBadge
            label={TYPE_LABELS[val] ?? val}
            className={TYPE_BADGE[val] ?? TYPE_BADGE.scout}
          />
        )
      },
    },
    {
      id: "membership_status",
      accessorKey: "membership_status",
      header: () => <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</span>,
      cell: ({ getValue }) => {
        const val = getValue<string>()
        if (val === "active") return null
        const cls = STATUS_BADGE[val] ?? STATUS_BADGE.inactive
        return <TintBadge label={val.charAt(0).toUpperCase() + val.slice(1)} className={cls} />
      },
    },
    {
      id: "email",
      accessorKey: "email",
      header: () => <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Email</span>,
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
