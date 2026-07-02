"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { sortableHeader } from "@/components/data-table"
import { formatMemberName } from "@/lib/format"
import type { Member, Group } from "@/types/api"

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

const GROUP_TYPE_BADGE: Record<string, string> = {
  patrol: "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300",
  custom: "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300",
}

const SYSTEM_BADGE = "bg-slate-100 text-slate-500 border border-slate-200 dark:bg-slate-800 dark:text-slate-400"

function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}

export function buildColumns(
  groupMap: Map<string, Group[]>,
  positionMap: Map<string, string>,
): ColumnDef<Member>[] {
  return [
    {
      id: "name",
      accessorFn: (row) => `${row.last_name} ${row.first_name}`,
      header: sortableHeader("Name"),
      cell: ({ row }) => {
        const m = row.original
        const display = formatMemberName(m)
        return <span className="font-medium">{display}</span>
      },
    },
    {
      id: "groups",
      accessorFn: (row) => {
        const memberGroups = groupMap.get(row.id) ?? []
        return memberGroups
          .map((g) => g.name)
          .sort()
          .join(", ")
      },
      header: sortableHeader("Groups"),
      cell: ({ row }) => {
        const memberGroups = groupMap.get(row.original.id) ?? []
        if (memberGroups.length === 0) {
          return <span className="text-muted-foreground">—</span>
        }

        const sortedGroups = [...memberGroups].sort((a, b) => {
          if (a.group_type === "patrol" && b.group_type !== "patrol") return -1
          if (a.group_type !== "patrol" && b.group_type === "patrol") return 1
          return a.name.localeCompare(b.name)
        })

        return (
          <div className="flex flex-wrap gap-1">
            {sortedGroups.map((g) => {
              let badgeClass = GROUP_TYPE_BADGE[g.group_type] ?? GROUP_TYPE_BADGE.custom
              if (g.is_system) {
                badgeClass = SYSTEM_BADGE
              }
              return (
                <TintBadge
                  key={g.id}
                  label={g.name}
                  className={badgeClass}
                />
              )
            })}
          </div>
        )
      },
    },
    {
      id: "position",
      accessorFn: (row) => positionMap.get(row.id) ?? "",
      header: sortableHeader("Position"),
      cell: ({ row }) => {
        const position = positionMap.get(row.original.id)
        return position ? (
          <span className="text-sm">{position}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )
      },
    },
    {
      id: "member_type",
      accessorKey: "member_type",
      header: sortableHeader("Type"),
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
      header: sortableHeader("Status"),
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
      header: sortableHeader("Email"),
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
