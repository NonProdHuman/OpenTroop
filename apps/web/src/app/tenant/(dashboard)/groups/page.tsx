"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Users, Lock, Plus, MoreHorizontal } from "lucide-react"
import { DataTable } from "@/components/data-table"
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
import { formatMemberName } from "@/lib/format"
import type { Group } from "@/types/api"
import { buildGroupColumns } from "./columns"
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
  DialogFooter,
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

  const columns = buildGroupColumns(memberCounts, (group) =>
    group.is_system ? (
      <span title="System group" className="text-muted-foreground flex justify-end">
        <Lock className="h-3.5 w-3.5" />
      </span>
    ) : (
      <GroupActionsDropdown
        group={group}
        onAddMember={() => setAddMemberGroup(group)}
        onViewDetails={() => setSelectedGroup(group)}
      />
    ),
  )

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

        {!isLoading && active.length === 0 ? (
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
        ) : (
          <DataTable
            data={filtered}
            columns={columns}
            isLoading={isLoading}
            onRowClick={setSelectedGroup}
            initialSorting={[{ id: "name", desc: false }]}
            emptyState={
              <p className="text-sm text-muted-foreground">No groups match &quot;{search}&quot;.</p>
            }
          />
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
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  function handleDelete() {
    deleteGroup.mutate(group.id, {
      onSuccess: () => {
        toast.success(`Deleted ${group.name}`)
        setDeleteDialogOpen(false)
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "Failed to delete group")
      },
    })
  }

  return (
    <>
      <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
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
            <DropdownMenuItem onClick={onAddMember}>Add member…</DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push(`/groups/${group.id}/edit`)}>
              Edit group
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onClick={() => {
                setDropdownOpen(false)
                setDeleteDialogOpen(true)
              }}
            >
              Delete group
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenu>

      {/* Confirmation dialog — rendered outside the dropdown so it survives the menu closing */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Delete group</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong>{group.name}</strong>? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteGroup.isPending}
            >
              {deleteGroup.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
                const name = formatMemberName(m)
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
