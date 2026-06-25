"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Users, Zap, Lock, Pencil, Trash2 } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useGroupMembers, useGroupRoleRules, useDeleteGroup } from "@/hooks/use-groups"
import { useRoles } from "@/hooks/use-roles"
import type { Group } from "@/types/api"

const TYPE_LABELS: Record<string, string> = {
  patrol: "Patrol",
  manual: "Manual",
  dynamic: "Dynamic",
}

function GroupTypeIcon({ group }: { group: Group }) {
  const cls = "h-4 w-4"
  if (group.is_system) return <Lock className={cls} />
  switch (group.group_type) {
    case "patrol":  return <Shield className={cls} />
    case "dynamic": return <Zap className={cls} />
    default:        return <Users className={cls} />
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  )
}

interface GroupDetailSheetProps {
  group: Group | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function GroupDetailSheet({ group, open, onOpenChange }: GroupDetailSheetProps) {
  const router = useRouter()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: members = [], isLoading: membersLoading } = useGroupMembers(group?.id ?? null)
  const { data: roleRules = [] } = useGroupRoleRules(
    group?.group_type === "dynamic" ? (group?.id ?? null) : null,
  )
  const { data: roles = [] } = useRoles()
  const deleteGroup = useDeleteGroup()

  const roleById = new Map(roles.map((r) => [r.id, r.name]))

  if (!group) return null

  function handleEdit() {
    onOpenChange(false)
    router.push(`/groups/${group!.id}/edit`)
  }

  function handleDelete() {
    deleteGroup.mutate(group!.id, {
      onSuccess: () => {
        setConfirmDelete(false)
        onOpenChange(false)
      },
    })
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) setConfirmDelete(false); onOpenChange(v) }}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="pb-4">
          <div className="flex items-center gap-2">
            {group.color ? (
              <span
                className="flex h-8 w-8 items-center justify-center rounded-full shrink-0"
                style={{ backgroundColor: `${group.color}25`, color: group.color }}
              >
                <GroupTypeIcon group={group} />
              </span>
            ) : (
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-muted shrink-0 text-muted-foreground">
                <GroupTypeIcon group={group} />
              </span>
            )}
            <SheetTitle className="text-xl">{group.name}</SheetTitle>
          </div>
          <SheetDescription className="sr-only">Group details</SheetDescription>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="secondary">{TYPE_LABELS[group.group_type] ?? group.group_type}</Badge>
            {group.is_system && <Badge variant="outline"><Lock className="h-3 w-3 mr-1" />System</Badge>}
          </div>

          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <Button size="sm" variant="outline" onClick={handleEdit}>
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Edit
            </Button>
            {!group.is_system && !confirmDelete && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmDelete(true)}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                Delete
              </Button>
            )}
            {!group.is_system && confirmDelete && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-destructive">Delete this group?</span>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteGroup.isPending}
                >
                  {deleteGroup.isPending ? "Deleting…" : "Confirm"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
              </div>
            )}
          </div>
        </SheetHeader>

        <div className="space-y-6">
          {group.description && (
            <Section title="Description">
              <p className="text-sm">{group.description}</p>
            </Section>
          )}

          <Section title={`Members (${membersLoading ? "…" : members.length})`}>
            {membersLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : members.length === 0 ? (
              <p className="text-sm text-muted-foreground">No members yet.</p>
            ) : (
              <ul className="space-y-1">
                {members.map((m) => {
                  const name = m.nickname
                    ? `${m.first_name} "${m.nickname}" ${m.last_name}`
                    : `${m.first_name} ${m.last_name}`
                  return (
                    <li key={m.id} className="flex items-center justify-between text-sm">
                      <button
                        type="button"
                        onClick={() => { onOpenChange(false); router.push(`/members/${m.id}`) }}
                        className="hover:underline text-left"
                      >
                        {name}
                      </button>
                      <Badge variant="outline" className="text-xs capitalize">
                        {m.member_type}
                      </Badge>
                    </li>
                  )
                })}
              </ul>
            )}
            {group.group_type === "dynamic" && (
              <p className="text-xs text-muted-foreground pt-1 italic">
                Membership is automatic — driven by role rules below.
              </p>
            )}
          </Section>

          {group.group_type === "dynamic" && roleRules.length > 0 && (
            <>
              <Separator />
              <Section title="Role Rules">
                <ul className="space-y-1">
                  {roleRules.map((rule) => (
                    <li key={rule.id} className="text-sm flex items-center gap-2">
                      <Zap className="h-3.5 w-3.5 text-violet-500 shrink-0" />
                      {roleById.get(rule.role_id) ?? rule.role_id}
                    </li>
                  ))}
                </ul>
              </Section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
