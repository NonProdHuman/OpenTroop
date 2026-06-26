"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Users, Zap, Lock, Plus, MoreHorizontal } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  useGroups,
  useGroupMemberCounts,
  useAddGroupMember,
  useGroupMembers,
  useDeleteGroup,
} from "@/hooks/use-groups"
import { useMembers } from "@/hooks/use-members"
import type { Group } from "@/types/api"
import { GroupDetailSheet } from "./group-detail-sheet"
import { toast } from "sonner"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuPortal,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"

const TYPE_LABELS: Record<string, string> = {
  patrol: "Patrol",
  manual: "Manual",
  dynamic: "Dynamic",
}

// Soft tinted badge classes for group types
const TYPE_BADGE: Record<string, string> = {
  patrol:  "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300",
  manual:  "bg-amber-50  text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300",
  dynamic: "bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950 dark:text-purple-300",
  system:  "bg-slate-100 text-slate-500 border border-slate-200 dark:bg-slate-800 dark:text-slate-400",
}

function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
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
  const [addMemberGroup, setAddMemberGroup] = useState<Group | null>(null)
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
    const badgeClass = group.is_system
      ? TYPE_BADGE.system
      : (TYPE_BADGE[group.group_type] ?? TYPE_BADGE.manual)
    return (
      <tr
        key={group.id}
        className="border-b last:border-0 hover:bg-muted/40 cursor-pointer transition-colors duration-75"
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
            <span className="font-medium text-sm">{group.name}</span>
          </div>
        </td>
        <td className="px-4 py-3">
          <TintBadge
            label={group.is_system ? "System" : (TYPE_LABELS[group.group_type] ?? group.group_type)}
            className={badgeClass}
          />
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground tabular-nums">
          {count !== undefined ? count : <span className="opacity-40">—</span>}
        </td>
        <td className="px-4 py-3 w-8 text-right" onClick={(e) => e.stopPropagation()}>
          {!group.is_system ? (
            <GroupActionsDropdown
              group={group}
              onAddMember={() => setAddMemberGroup(group)}
              onViewDetails={() => setSelectedGroup(group)}
            />
          ) : (
            <span title="System group" className="text-muted-foreground flex justify-end">
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

      {addMemberGroup && (
        <AddMemberDialog
          group={addMemberGroup}
          open={true}
          onOpenChange={(v) => { if (!v) setAddMemberGroup(null) }}
        />
      )}

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
          <div className="rounded-lg border border-dashed p-12 text-center">
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-muted p-4">
                <Users className="h-7 w-7 text-muted-foreground" />
              </div>
            </div>
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
              <div className="rounded-lg border shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      <th className="px-4 py-2.5 text-left">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Name</span>
                      </th>
                      <th className="px-4 py-2.5 text-left">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Type</span>
                      </th>
                      <th className="px-4 py-2.5 text-left">
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Members</span>
                      </th>
                      <th className="px-4 py-2.5 w-8" />
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
                <div className="rounded-lg border shadow-sm overflow-hidden">
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

function GroupActionsDropdown({
  group,
  onAddMember,
  onViewDetails,
}: {
  group: Group
  onAddMember: () => void
  onViewDetails: () => void
}) {
  const router = useRouter()
  const deleteGroup = useDeleteGroup()
  const [open, setOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    deleteGroup.mutate(group.id, {
      onSuccess: () => {
        toast.success(`Deleted ${group.name}`)
        setOpen(false)
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "Failed to delete group")
      },
    })
  }

  return (
    <DropdownMenu open={open} onOpenChange={(o) => { setOpen(o); if (!o) setConfirmDelete(false); }}>
      <DropdownMenuTrigger
        render={
          <Button
            size="icon-sm"
            variant="ghost"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
          >
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Actions</span>
          </Button>
        }
      />
      <DropdownMenuPortal>
        <DropdownMenuContent align="end" className="w-36">
          <DropdownMenuItem onClick={onViewDetails}>View details</DropdownMenuItem>
          {!group.is_system && group.group_type !== "dynamic" && (
            <DropdownMenuItem onClick={onAddMember}>Add member…</DropdownMenuItem>
          )}
          {!group.is_system && (
            <DropdownMenuItem onClick={() => router.push(`/groups/${group.id}/edit`)}>
              Edit group
            </DropdownMenuItem>
          )}
          {!group.is_system && <DropdownMenuSeparator />}
          {!group.is_system && (
            <DropdownMenuItem
              variant="destructive"
              onClick={confirmDelete ? handleDelete : () => setConfirmDelete(true)}
            >
              {confirmDelete ? "Confirm delete" : "Delete group"}
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenu>
  )
}

function AddMemberDialog({
  group,
  open,
  onOpenChange,
}: {
  group: Group
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: members = [] } = useGroupMembers(group.id)
  const { data: allMembers = [] } = useMembers()
  const addMember = useAddGroupMember()

  const memberIds = new Set(members.map((m) => m.id))
  const addableMembers = allMembers.filter((m) => {
    if (m.is_deleted) return false
    if (memberIds.has(m.id)) return false
    if (group.group_type === "patrol" && m.member_type === "adult") return false
    return true
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Add Member to {group.name}</DialogTitle>
          <DialogDescription>
            Search and select a member to add to this group.
          </DialogDescription>
        </DialogHeader>
        <Command className="border rounded-lg mt-2">
          <CommandInput placeholder="Search members…" className="h-8" />
          <CommandList className="max-h-64">
            <CommandEmpty>
              {addableMembers.length === 0
                ? "All members are already in this group."
                : "No members found."}
            </CommandEmpty>
            <CommandGroup>
              {addableMembers.map((m) => {
                const name = m.nickname
                  ? `${m.first_name} "${m.nickname}" ${m.last_name}`
                  : `${m.first_name} ${m.last_name}`
                return (
                  <CommandItem
                    key={m.id}
                    value={name}
                    onSelect={() => {
                      addMember.mutate(
                        { groupId: group.id, memberId: m.id },
                        {
                          onSuccess: () => {
                            toast.success(`Added ${m.first_name} to ${group.name}`)
                            onOpenChange(false)
                          },
                          onError: (err) => {
                            toast.error(
                              err instanceof Error ? err.message : "Failed to add member"
                            )
                          },
                        }
                      )
                    }}
                    className="flex items-center justify-between py-2 px-3 text-sm cursor-pointer hover:bg-muted/50 rounded-md"
                  >
                    <span>{name}</span>
                    <span className="text-xs text-muted-foreground capitalize shrink-0 ml-2">
                      {m.member_type}
                    </span>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  )
}
