"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { X, Lock, Zap } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import {
  useGroup,
  useGroupMembers,
  useGroupRoleRules,
  useUpdateGroup,
  useAddGroupMember,
  useRemoveGroupMember,
  useRemoveGroupRoleRule,
} from "@/hooks/use-groups"
import { useMembers } from "@/hooks/use-members"
import { useRoles } from "@/hooks/use-roles"
import type { Group, GroupType } from "@/types/api"

const PRESET_COLORS = [
  { hex: "#F59E0B", label: "Amber" },
  { hex: "#3B82F6", label: "Blue" },
  { hex: "#10B981", label: "Emerald" },
  { hex: "#EF4444", label: "Red" },
  { hex: "#8B5CF6", label: "Violet" },
  { hex: "#EC4899", label: "Pink" },
  { hex: "#F97316", label: "Orange" },
  { hex: "#14B8A6", label: "Teal" },
]

function ColorPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {PRESET_COLORS.map(({ hex, label }) => (
          <button
            key={hex}
            type="button"
            onClick={() => onChange(hex)}
            aria-label={label}
            className="h-8 w-8 rounded-full transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            style={{
              backgroundColor: hex,
              outline: value === hex ? `3px solid ${hex}` : "3px solid transparent",
              outlineOffset: "2px",
            }}
          />
        ))}
      </div>
      <div className="flex items-center gap-2">
        <span
          className="h-6 w-6 rounded-full border border-border shrink-0"
          style={{ backgroundColor: value }}
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#000000"
          className="h-7 w-28 font-mono text-xs"
          maxLength={7}
        />
      </div>
    </div>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground pt-2">
      {children}
    </h2>
  )
}

export default function GroupEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: group, isLoading } = useGroup(id)

  if (isLoading || !group) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
  }

  return <GroupEditForm id={id} group={group} />
}

function GroupEditForm({ id, group }: { id: string; group: Group }) {
  const router = useRouter()

  const { data: members = [] } = useGroupMembers(id)
  const { data: roleRules = [] } = useGroupRoleRules(
    group.group_type === "dynamic" ? id : null,
  )
  const { data: allMembers = [] } = useMembers()
  const { data: allRoles = [] } = useRoles()

  const updateGroup = useUpdateGroup()
  const addMember = useAddGroupMember()
  const removeMember = useRemoveGroupMember()
  const removeRule = useRemoveGroupRoleRule()

  const [name, setName] = useState(group.name)
  const [type, setType] = useState<GroupType>(group.group_type)
  const [color, setColor] = useState(group.color ?? PRESET_COLORS[0].hex)
  const [description, setDescription] = useState(group.description ?? "")
  const [nameError, setNameError] = useState<string | null>(null)
  const [addMemberOpen, setAddMemberOpen] = useState(false)

  const isSystem = group.is_system
  const isDynamic = group.group_type === "dynamic"
  const memberIds = new Set(members.map((m) => m.id))

  const addableMembers = allMembers.filter((m) => {
    if (m.is_deleted) return false
    if (memberIds.has(m.id)) return false
    if (type === "patrol" && m.member_type === "adult") return false
    return true
  })

  const roleById = new Map(allRoles.map((r) => [r.id, r.name]))

  async function handleSave() {
    if (!name.trim()) { setNameError("Name is required."); return }
    setNameError(null)
    updateGroup.mutate(
      { id, data: { name: name.trim(), group_type: type, color, description: description.trim() || null } },
      {
        onSuccess: () => router.push("/groups"),
        onError: (err) => {
          const msg = err instanceof Error ? err.message : ""
          if (msg.includes("409")) setNameError("A group with this name already exists.")
          else setNameError("Something went wrong — please try again.")
        },
      },
    )
  }

  function displayName(m: { first_name: string; last_name: string; nickname: string | null }) {
    return m.nickname ? `${m.first_name} "${m.nickname}" ${m.last_name}` : `${m.first_name} ${m.last_name}`
  }

  return (
    <>
      <PageHeader title={`Edit — ${group.name}`}>
        <Button variant="outline" onClick={() => router.push("/groups")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updateGroup.isPending}>
          {updateGroup.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6">
        {isSystem && (
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
            <Lock className="h-4 w-4 shrink-0" />
            System group — name and type cannot be changed.
          </div>
        )}

        {/* ── Identity ─────────────────────────────────────── */}
        <FormField label="Name">
          {isSystem ? (
            <p className="text-sm font-medium py-1">{group.name}</p>
          ) : (
            <>
              <Input
                value={name}
                onChange={(e) => { setName(e.target.value); setNameError(null) }}
                autoFocus={!isSystem}
              />
              {nameError && <p className="text-sm text-destructive mt-1">{nameError}</p>}
            </>
          )}
        </FormField>

        <FormField label="Type">
          {isSystem || isDynamic ? (
            <Badge variant="secondary" className="capitalize">{group.group_type}</Badge>
          ) : (
            <Select value={type} onValueChange={(v) => setType(v as GroupType)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="patrol">Patrol</SelectItem>
                <SelectItem value="manual">Manual group</SelectItem>
              </SelectContent>
            </Select>
          )}
        </FormField>

        <FormField label="Color">
          <ColorPicker value={color} onChange={setColor} />
        </FormField>

        <FormField label="Description">
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional — describe this group's purpose"
            rows={3}
          />
        </FormField>

        <Separator />

        {/* ── Members ──────────────────────────────────────── */}
        <SectionTitle>Members</SectionTitle>
        <div className="space-y-2">
          {members.length === 0 ? (
            <p className="text-sm text-muted-foreground">No members yet.</p>
          ) : (
            <ul className="divide-y rounded-md border">
              {members.map((m) => (
                <li key={m.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>{displayName(m)}</span>
                  {!isDynamic && !isSystem && (
                    <button
                      type="button"
                      onClick={() => removeMember.mutate({ groupId: id, memberId: m.id })}
                      disabled={removeMember.isPending}
                      className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                      aria-label={`Remove ${displayName(m)}`}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {!isDynamic && !isSystem && (
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
                      {addableMembers.map((m) => (
                        <CommandItem
                          key={m.id}
                          value={displayName(m)}
                          onSelect={() => {
                            addMember.mutate({ groupId: id, memberId: m.id })
                            setAddMemberOpen(false)
                          }}
                        >
                          {displayName(m)}
                          <span className="ml-auto text-xs text-muted-foreground capitalize">
                            {m.member_type}
                          </span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}

          {isDynamic && (
            <p className="text-xs text-muted-foreground italic">
              Members are resolved automatically from role rules below.
            </p>
          )}
        </div>

        {/* ── Role Rules (dynamic only) ─────────────────────── */}
        {isDynamic && (
          <>
            <Separator />
            <SectionTitle>Role Rules</SectionTitle>
            <div className="space-y-2">
              {roleRules.length === 0 ? (
                <p className="text-sm text-muted-foreground">No role rules defined.</p>
              ) : (
                <ul className="divide-y rounded-md border">
                  {roleRules.map((rule) => (
                    <li key={rule.id} className="flex items-center justify-between px-3 py-2 text-sm">
                      <div className="flex items-center gap-2">
                        <Zap className="h-3.5 w-3.5 text-violet-500 shrink-0" />
                        {roleById.get(rule.role_id) ?? rule.role_id}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeRule.mutate({ groupId: id, roleId: rule.role_id })}
                        disabled={removeRule.isPending}
                        className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                        aria-label="Remove rule"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted-foreground">
                Adding new role rules via the UI is coming soon.
              </p>
            </div>
          </>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/groups")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateGroup.isPending}>
            {updateGroup.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </>
  )
}
