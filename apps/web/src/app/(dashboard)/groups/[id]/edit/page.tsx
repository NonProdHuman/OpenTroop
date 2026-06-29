"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { X, Lock } from "lucide-react"
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
import { MultiSelectChips } from "@/components/multi-select-chips"
import {
  useGroup,
  useGroupMembers,
  useGroupRules,
  useUpsertGroupRule,
  useDeleteGroupRule,
  useUpdateGroup,
  useAddGroupMember,
  useRemoveGroupMember,
  useGroups,
} from "@/hooks/use-groups"
import { useMembers } from "@/hooks/use-members"
import { usePositions } from "@/hooks/use-positions"
import type { Group, GroupType, RuleLogic, RuleDimension } from "@/types/api"

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
  const { data: rules = [] } = useGroupRules(id)
  const { data: allMembers = [] } = useMembers()
  const { data: allPositions = [] } = usePositions()
  const { data: allGroups = [] } = useGroups()

  const updateGroup = useUpdateGroup()
  const addMember = useAddGroupMember()
  const removeMember = useRemoveGroupMember()

  const upsertRule = useUpsertGroupRule()
  const deleteRule = useDeleteGroupRule()

  const [name, setName] = useState(group.name)
  const [type, setType] = useState<GroupType>(group.group_type)
  const [color, setColor] = useState(group.color ?? PRESET_COLORS[0].hex)
  const [description, setDescription] = useState(group.description ?? "")
  const [ruleLogic, setRuleLogic] = useState<RuleLogic>(group.rule_logic)
  const [includeParents, setIncludeParents] = useState(group.include_parents)
  const [ccParents, setCcParents] = useState(group.cc_parents_on_messages)
  const [nameError, setNameError] = useState<string | null>(null)

  const [addMemberOpen, setAddMemberOpen] = useState(false)

  // Local state to keep track of dimensions that have been checked (expanded) by the user
  // but do not yet have saved filters in the database.
  const [expandedDimensions, setExpandedDimensions] = useState<Set<RuleDimension>>(new Set())

  const isSystem = group.is_system
  const memberIds = new Set(members.map((m) => m.id))

  const addableMembers = allMembers.filter((m) => {
    if (m.is_deleted) return false
    if (memberIds.has(m.id)) return false
    if (type === "patrol" && m.member_type === "adult") return false
    return true
  })


  const activeRulesMap = new Map(rules.filter(r => !r.is_deleted).map(r => [r.dimension, r]))

  async function handleSave() {
    if (!name.trim()) { setNameError("Name is required."); return }
    setNameError(null)
    updateGroup.mutate(
      { id, data: { name: name.trim(), group_type: type, color, description: description.trim() || null, rule_logic: ruleLogic, include_parents: includeParents, cc_parents_on_messages: ccParents } },
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

  // Toggle rule for boolean dimensions (OA member/active) which do not require additional configuration
  function handleRuleToggle(dimension: RuleDimension, enabled: boolean) {
    if (enabled) {
      upsertRule.mutate({ groupId: id, dimension, values: [] })
    } else {
      deleteRule.mutate({ groupId: id, dimension })
    }
  }

  // Expand/collapse multi-select dimensions locally first before they select values
  function toggleExpandDimension(dimension: RuleDimension, checked: boolean) {
    if (checked) {
      setExpandedDimensions((prev) => {
        const next = new Set(prev)
        next.add(dimension)
        return next
      })
    } else {
      setExpandedDimensions((prev) => {
        const next = new Set(prev)
        next.delete(dimension)
        return next
      })
      if (activeRulesMap.has(dimension)) {
        deleteRule.mutate({ groupId: id, dimension })
      }
    }
  }

  // Helper to save rule values to the backend
  function handleRuleSave(dimension: RuleDimension, values: string[] | null) {
    upsertRule.mutate({ groupId: id, dimension, values })
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

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6 pb-20">
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
          {isSystem ? (
            <Badge variant="secondary" className="capitalize">{group.group_type}</Badge>
          ) : (
            <Select value={type} onValueChange={(v) => setType(v as GroupType)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="custom">Custom group</SelectItem>
                <SelectItem value="patrol">Patrol</SelectItem>
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
            <ul className="divide-y rounded-md border max-h-60 overflow-y-auto">
              {members.map((m) => (
                <li key={m.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>{displayName(m)}</span>
                  {!isSystem && (
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

          {!isSystem && (
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

          {type === "custom" && (
            <p className="text-xs text-muted-foreground italic">
              Members added here are combined with anyone matching the rules below.
            </p>
          )}
        </div>

        {/* ── Dynamic Rules (custom only) ─────────────────── */}
        {type === "custom" && (
          <>
            <Separator />
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <SectionTitle>Dynamic Rules</SectionTitle>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Logic Mode:</span>
                  <Select value={ruleLogic} onValueChange={(v) => setRuleLogic(v as RuleLogic)}>
                    <SelectTrigger className="h-7 w-28 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="and">ALL (AND)</SelectItem>
                      <SelectItem value="or">ANY (OR)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-3">
                {/* 1. Member Type Rule */}
                <RuleRow
                  label="Filter by Member Type"
                  enabled={activeRulesMap.has("member_type") || expandedDimensions.has("member_type")}
                  onToggle={(checked) => toggleExpandDimension("member_type", checked)}
                >
                  <div className="flex gap-4">
                    {["scout", "adult"].map((t) => {
                      const currentVals = activeRulesMap.get("member_type")?.values || []
                      const checked = currentVals.includes(t)
                      return (
                        <label key={t} className="text-xs flex items-center gap-1.5 cursor-pointer capitalize">
                          <input
                            type="checkbox"
                            checked={checked}
                            className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                            onChange={() => {
                              const next = checked
                                ? currentVals.filter((x) => x !== t)
                                : [...currentVals, t]
                              if (next.length === 0) {
                                toggleExpandDimension("member_type", false)
                              } else {
                                handleRuleSave("member_type", next)
                              }
                            }}
                          />
                          {t}s
                        </label>
                      )
                    })}
                  </div>
                </RuleRow>

                {/* 2. Membership Status Rule */}
                <RuleRow
                  label="Filter by Membership Status"
                  enabled={activeRulesMap.has("membership_status") || expandedDimensions.has("membership_status")}
                  onToggle={(checked) => toggleExpandDimension("membership_status", checked)}
                >
                  <div className="flex gap-4">
                    {["active", "inactive", "alumni"].map((s) => {
                      const currentVals = activeRulesMap.get("membership_status")?.values || []
                      const checked = currentVals.includes(s)
                      return (
                        <label key={s} className="text-xs flex items-center gap-1.5 cursor-pointer capitalize">
                          <input
                            type="checkbox"
                            checked={checked}
                            className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                            onChange={() => {
                              const next = checked
                                ? currentVals.filter((x) => x !== s)
                                : [...currentVals, s]
                              if (next.length === 0) {
                                toggleExpandDimension("membership_status", false)
                              } else {
                                handleRuleSave("membership_status", next)
                              }
                            }}
                          />
                          {s}
                        </label>
                      )
                    })}
                  </div>
                </RuleRow>

                {/* 3. Is OA Member */}
                <RuleRow
                  label="Only Order of the Arrow Members"
                  enabled={activeRulesMap.has("oa_member")}
                  onToggle={(checked) => handleRuleToggle("oa_member", checked)}
                />

                {/* 4. Is OA Active */}
                <RuleRow
                  label="Only Active Order of the Arrow Members"
                  enabled={activeRulesMap.has("oa_active")}
                  onToggle={(checked) => handleRuleToggle("oa_active", checked)}
                />

                {/* 5. Position Rule */}
                <RuleRow
                  label="Filter by Position(s)"
                  enabled={activeRulesMap.has("position") || expandedDimensions.has("position")}
                  onToggle={(checked) => toggleExpandDimension("position", checked)}
                >
                  <MultiSelectChips
                    options={allPositions.filter((p) => !p.is_deleted).map((p) => ({ id: p.id, label: p.name }))}
                    selectedIds={activeRulesMap.get("position")?.values || []}
                    onChange={(next) =>
                      next.length === 0
                        ? toggleExpandDimension("position", false)
                        : handleRuleSave("position", next)
                    }
                    addLabel="Add position…"
                    searchPlaceholder="Search positions…"
                    emptyLabel="No positions found."
                  />
                </RuleRow>

                {/* 6. Group Member Rule */}
                <RuleRow
                  label="Filter by Group Membership"
                  enabled={activeRulesMap.has("group_member") || expandedDimensions.has("group_member")}
                  onToggle={(checked) => toggleExpandDimension("group_member", checked)}
                >
                  <MultiSelectChips
                    options={allGroups
                      .filter((g) => g.id !== group.id && !g.is_deleted)
                      .map((g) => ({ id: g.id, label: g.name }))}
                    selectedIds={activeRulesMap.get("group_member")?.values || []}
                    onChange={(next) =>
                      next.length === 0
                        ? toggleExpandDimension("group_member", false)
                        : handleRuleSave("group_member", next)
                    }
                    addLabel="Add group…"
                    searchPlaceholder="Search groups…"
                    emptyLabel="No groups found."
                  />
                </RuleRow>

                {/* 7. Rank Rule (Phase 2 - Disabled) */}
                <RuleRow
                  label="Filter by Rank(s)"
                  enabled={false}
                  disabled={true}
                  comingSoon={true}
                  onToggle={() => {}}
                />
              </div>

              {/* Parent options — applied AFTER the rules resolve. */}
              <div className="space-y-3 pt-1">
                <SectionTitle>Parents &amp; Guardians</SectionTitle>
                <ParentToggle
                  label="Include parents/guardians as members"
                  hint="Also add the parents/guardians of everyone resolved above to this group."
                  checked={includeParents}
                  onChange={setIncludeParents}
                />
                <ParentToggle
                  label="Send messages to parents/guardians"
                  hint="When you message this group, also include parents/guardians (coming soon)."
                  checked={includeParents || ccParents}
                  disabled={includeParents}
                  onChange={setCcParents}
                />
              </div>
            </div>
          </>
        )}

        {/* ── Patrol: communications-only parent option ───── */}
        {type === "patrol" && !isSystem && (
          <>
            <Separator />
            <div className="space-y-3">
              <SectionTitle>Parents &amp; Guardians</SectionTitle>
              <ParentToggle
                label="Send messages to parents/guardians"
                hint="When you message this patrol, also include parents/guardians (coming soon). Parents do not become patrol members."
                checked={ccParents}
                onChange={setCcParents}
              />
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

interface RuleRowProps {
  label: string
  enabled: boolean
  onToggle: (checked: boolean) => void
  disabled?: boolean
  comingSoon?: boolean
  children?: React.ReactNode
}

function RuleRow({ label, enabled, onToggle, disabled, comingSoon, children }: RuleRowProps) {
  return (
    <div className="space-y-2 p-3 rounded-md border bg-muted/20">
      <div className="flex items-center justify-between">
        <label className={cn("text-sm font-medium flex items-center gap-2 cursor-pointer select-none", disabled && "opacity-50 cursor-not-allowed")}>
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer disabled:cursor-not-allowed"
            checked={enabled}
            disabled={disabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          <span>{label}</span>
          {comingSoon && <span className="text-xs text-muted-foreground font-normal">{comingSoon}</span>}
        </label>
      </div>
      {enabled && children && (
        <div className="pl-6 pt-1 space-y-2">
          {children}
        </div>
      )}
    </div>
  )
}

interface ParentToggleProps {
  label: string
  hint: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}

function ParentToggle({ label, hint, checked, disabled, onChange }: ParentToggleProps) {
  return (
    <label
      className={cn(
        "flex items-start gap-2 p-3 rounded-md border bg-muted/20 cursor-pointer select-none",
        disabled && "opacity-60 cursor-not-allowed",
      )}
    >
      <input
        type="checkbox"
        className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer disabled:cursor-not-allowed"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="space-y-0.5">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground font-normal">{hint}</span>
      </span>
    </label>
  )
}
