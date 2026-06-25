"use client"

import { PageHeader } from "@/components/page-header"
import { Badge } from "@/components/ui/badge"
import { useGroups } from "@/hooks/use-groups"

const TYPE_LABELS: Record<string, string> = {
  manual: "Manual",
  dynamic: "Dynamic",
  patrol: "Patrol",
}

export default function GroupsPage() {
  const { data: groups = [], isLoading } = useGroups()

  return (
    <>
      <PageHeader title={`Groups (${groups.length})`} />
      <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
        <p className="text-muted-foreground text-sm">
          Groups are the building block for event visibility and messaging. Patrols are
          groups too. Full management — members and dynamic role rules — is coming soon.
        </p>

        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : groups.length === 0 ? (
          <p className="text-muted-foreground text-sm">No groups yet.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {groups.map((group) => (
              <li
                key={group.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="flex items-center gap-2">
                  {group.color ? (
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: group.color }}
                    />
                  ) : null}
                  <span className="font-medium">{group.name}</span>
                </div>
                <Badge variant="secondary">
                  {TYPE_LABELS[group.group_type] ?? group.group_type}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}
