"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Users, Zap, Lock, Pencil, Trash2, X } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  useGroupMembers,
  useGroupRules,
  useDeleteGroup,
  useAddGroupMember,
  useRemoveGroupMember,
  useGroups,
} from "@/hooks/use-groups"
import { usePositions } from "@/hooks/use-positions"
import { useMembers } from "@/hooks/use-members"
import type { Group, GroupRule } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
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
  custom: "Custom",
}

function GroupTypeIcon({ group }: { group: Group }) {
  const cls = "h-4 w-4"
  if (group.is_system) return <Lock className={cls} />
  switch (group.group_type) {
    case "patrol":  return <Shield className={cls} />
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
  const [addMemberOpen, setAddMemberOpen] = useState(false)

  const { data: members = [], isLoading: membersLoading } = useGroupMembers(group?.id ?? null)
  const { data: rules = [] } = useGroupRules(group?.id ?? null)
  const { data: positions = [] } = usePositions()
  const { data: groups = [] } = useGroups()
  const { data: allMembers = [] } = useMembers()

  const deleteGroup = useDeleteGroup()
  const addMember = useAddGroupMember()
  const removeMember = useRemoveGroupMember()

  const positionById = new Map(positions.map((p) => [p.id, p.name]))
  const groupById = new Map(groups.map((g) => [g.id, g.name]))

  if (!group) return null

  const isSystem = group.is_system
  const memberIds = new Set(members.map((m) => m.id))
  const addableMembers = allMembers.filter((m) => {
    if (m.is_deleted) return false
    if (memberIds.has(m.id)) return false
    if (group.group_type === "patrol" && m.member_type === "adult") return false
    return true
  })

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

  function getRuleLabel(rule: GroupRule) {
    switch (rule.dimension) {
      case "member_type":
        return `Member type: ${rule.values?.map((v: string) => v === "scout" ? "Scouts" : "Adults").join(", ")}`
      case "membership_status":
        return `Status: ${rule.values?.map((v: string) => v === "active" ? "Active" : v === "inactive" ? "Inactive" : "Alumni").join(", ")}`
      case "oa_member":
        return "Is OA Member"
      case "oa_active":
        return "Is active OA Member"
      case "position":
        return `Positions: ${rule.values?.map((id: string) => positionById.get(id) ?? id).join(", ")}`
      case "group_member":
        return `In Group(s): ${rule.values?.map((id: string) => groupById.get(id) ?? id).join(", ")}`
      case "rank":
        return `Ranks: ${rule.values?.join(", ")}`
      default:
        return `${rule.dimension}: ${rule.values?.join(", ") ?? ""}`
    }
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
                      <div className="flex items-center gap-1.5 min-w-0">
                        <button
                          type="button"
                          onClick={() => { onOpenChange(false); router.push(`/members/${m.id}`) }}
                          className="hover:underline text-left truncate font-medium text-slate-700 dark:text-slate-200"
                        >
                          {name}
                        </button>
                        {!isSystem && (
                          <button
                            type="button"
                            onClick={() =>
                              removeMember.mutate(
                                { groupId: group.id, memberId: m.id },
                                {
                                  onSuccess: () => {
                                    toast.success(`Removed ${m.first_name} from ${group.name}`)
                                  },
                                  onError: (err) => {
                                    toast.error(
                                      err instanceof Error ? err.message : "Failed to remove member"
                                    )
                                  },
                                }
                              )
                            }
                            disabled={removeMember.isPending}
                            className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                            aria-label={`Remove ${name}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                      <Badge variant="outline" className="text-xs capitalize shrink-0">
                        {m.member_type}
                      </Badge>
                    </li>
                  )
                })}
              </ul>
            )}
            {!isSystem && (
              <div className="pt-2">
                <Popover open={addMemberOpen} onOpenChange={setAddMemberOpen}>
                  <PopoverTrigger
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "h-7 text-xs gap-1")}
                    aria-expanded={addMemberOpen}
                  >
                    Add member…
                  </PopoverTrigger>
                  <PopoverContent className="w-64 p-0" align="start">
                    <Command>
                      <CommandInput placeholder="Search members…" className="h-8" />
                      <CommandList>
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
                                      },
                                      onError: (err) => {
                                        toast.error(
                                          err instanceof Error ? err.message : "Failed to add member"
                                        )
                                      },
                                    }
                                  )
                                  setAddMemberOpen(false)
                                }}
                              >
                                {name}
                                <span className="ml-auto text-xs text-muted-foreground capitalize">
                                  {m.member_type}
                                </span>
                              </CommandItem>
                            )
                          })}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
            )}
            {rules.length > 0 && (
              <p className="text-xs text-muted-foreground pt-1 italic">
                Plus members matching the rules below (logic: {group.rule_logic.toUpperCase()}).
                {group.include_parents && " Parents/guardians of resolved members are included."}
              </p>
            )}
          </Section>

          {rules.length > 0 && (
            <>
              <Separator />
              <Section title="Dynamic Rules">
                <ul className="space-y-2">
                  {rules.map((rule) => (
                    <li key={rule.id} className="text-sm flex items-start gap-2">
                      <Zap className="h-4 w-4 text-violet-500 shrink-0 mt-0.5" />
                      <div>{getRuleLabel(rule)}</div>
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
