"use client"

import { type ColumnDef } from "@tanstack/react-table"
import { Lock, Shield, Users } from "lucide-react"
import { sortableHeader } from "@/components/data-table"
import type { Group } from "@/types/api"

const TYPE_LABELS: Record<string, string> = {
  patrol: "Patrol",
  custom: "Custom",
}

// Soft tinted badge classes for group types
const TYPE_BADGE: Record<string, string> = {
  patrol: "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300",
  custom: "bg-amber-50  text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300",
  system: "bg-slate-100 text-slate-500 border border-slate-200 dark:bg-slate-800 dark:text-slate-400",
}

function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}

function typeLabel(group: Group): string {
  return group.is_system ? "System" : (TYPE_LABELS[group.group_type] ?? group.group_type)
}

export function buildGroupColumns(
  memberCounts: Map<string, number>,
  renderActions: (group: Group) => React.ReactNode,
): ColumnDef<Group>[] {
  return [
    {
      id: "name",
      accessorKey: "name",
      header: sortableHeader("Name"),
      cell: ({ row }) => {
        const group = row.original
        const Icon = group.group_type === "patrol" ? Shield : Users
        return (
          <div className="flex items-center gap-2.5">
            <span
              className="flex h-7 w-7 items-center justify-center rounded-full shrink-0"
              style={
                group.color
                  ? { backgroundColor: `${group.color}25`, color: group.color }
                  : undefined
              }
              aria-hidden
            >
              <Icon className="h-3.5 w-3.5 text-muted-foreground" />
            </span>
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{group.name}</span>
              {group.is_system && <Lock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
            </div>
          </div>
        )
      },
    },
    {
      id: "group_type",
      accessorFn: (row) => typeLabel(row),
      header: sortableHeader("Type"),
      cell: ({ row }) => {
        const group = row.original
        const badgeClass = group.is_system
          ? TYPE_BADGE.system
          : (TYPE_BADGE[group.group_type] ?? TYPE_BADGE.custom)
        return <TintBadge label={typeLabel(group)} className={badgeClass} />
      },
    },
    {
      id: "member_count",
      accessorFn: (row) => memberCounts.get(row.id) ?? -1, // unknown counts sort first
      header: sortableHeader("Members"),
      cell: ({ row }) => {
        const count = memberCounts.get(row.original.id)
        return (
          <span className="text-sm text-muted-foreground tabular-nums">
            {count !== undefined ? count : <span className="opacity-40">—</span>}
          </span>
        )
      },
    },
    {
      id: "actions",
      enableSorting: false,
      header: () => null,
      meta: { className: "w-8 text-right" },
      cell: ({ row }) => (
        // Stop propagation so the actions menu doesn't also open the detail sheet.
        <div onClick={(e) => e.stopPropagation()}>{renderActions(row.original)}</div>
      ),
    },
  ]
}
