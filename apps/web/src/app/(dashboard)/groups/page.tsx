"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Users, Zap, Lock, Plus } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useGroups, useGroupMemberCounts } from "@/hooks/use-groups"
import type { Group } from "@/types/api"
import { GroupDetailSheet } from "./group-detail-sheet"

const TYPE_LABELS: Record<string, string> = {
  patrol: "Patrol",
  manual: "Manual",
  dynamic: "Dynamic",
}

function GroupTypeIcon({ group, className }: { group: Group; className?: string }) {
  if (group.is_system) return <Lock className={className} />
  switch (group.group_type) {
    case "patrol":  return <Shield className={className} />
    case "dynamic": return <Zap className={className} />
    default:        return <Users className={className} />
  }
}

export default function GroupsPage() {
  const router = useRouter()
  const [search, setSearch] = useState("")
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null)
  const { data: groups = [], isLoading } = useGroups()

  const active = groups.filter((g) => !g.is_deleted)
  const memberCounts = useGroupMemberCounts(active)

  const filtered = active.filter((g) =>
    g.name.toLowerCase().includes(search.toLowerCase()),
  )
  const nonSystem = filtered.filter((g) => !g.is_system)
  const system = filtered.filter((g) => g.is_system)

  function GroupRow({ group }: { group: Group }) {
    const count = memberCounts.get(group.id)
    return (
      <tr
        key={group.id}
        className="border-b last:border-0 hover:bg-muted/50 cursor-pointer transition-colors"
        onClick={() => setSelectedGroup(group)}
      >
        <td className="px-4 py-3">
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
              <GroupTypeIcon group={group} className="h-3.5 w-3.5 text-muted-foreground" />
            </span>
            <span className="font-medium">{group.name}</span>
          </div>
        </td>
        <td className="px-4 py-3">
          <Badge variant="secondary" className="capitalize">
            {TYPE_LABELS[group.group_type] ?? group.group_type}
          </Badge>
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground tabular-nums">
          {count !== undefined ? count : <span className="opacity-40">—</span>}
        </td>
        <td className="px-4 py-3">
          {group.is_system && (
            <span title="System group" className="text-muted-foreground">
              <Lock className="h-3.5 w-3.5" />
            </span>
          )}
        </td>
      </tr>
    )
  }

  return (
    <>
      <PageHeader title={`Groups (${active.length})`}>
        <Button size="sm" onClick={() => router.push("/groups/new")}>
          <Plus className="h-4 w-4 mr-1" />
          New group
        </Button>
      </PageHeader>

      <GroupDetailSheet
        group={selectedGroup}
        open={selectedGroup !== null}
        onOpenChange={(v) => { if (!v) setSelectedGroup(null) }}
      />

      <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
        <div className="flex items-center gap-3 max-w-sm">
          <Input
            placeholder="Search groups…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8"
          />
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : active.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <Users className="mx-auto h-8 w-8 text-muted-foreground/50 mb-3" />
            <p className="font-medium mb-1">No groups yet</p>
            <p className="text-sm text-muted-foreground mb-4">
              Create a patrol or group to organize your troop.
            </p>
            <Button size="sm" onClick={() => router.push("/groups/new")}>
              <Plus className="h-4 w-4 mr-1" />
              New group
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">No groups match &quot;{search}&quot;.</p>
        ) : (
          <div className="space-y-6">
            {nonSystem.length > 0 && (
              <div className="rounded-md border overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">Name</th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">Type</th>
                      <th className="px-4 py-2 text-left font-medium text-muted-foreground">Members</th>
                      <th className="px-4 py-2 w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {nonSystem.map((g) => <GroupRow key={g.id} group={g} />)}
                  </tbody>
                </table>
              </div>
            )}

            {system.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 px-1">
                  System groups
                </p>
                <div className="rounded-md border overflow-hidden">
                  <table className="w-full text-sm">
                    <tbody>
                      {system.map((g) => <GroupRow key={g.id} group={g} />)}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
