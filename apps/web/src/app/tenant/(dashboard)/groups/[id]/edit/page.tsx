"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Lock } from "lucide-react"
import { apiErrorMessage } from "@/lib/api"
import { ColorPicker, PRESET_COLORS } from "@/components/color-picker"
import { FormField, SectionTitle } from "@/components/form-helpers"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
  useGroup,
  useGroupMembers,
  useGroupManualMembers,
  useUpdateGroup,
} from "@/hooks/use-groups"
import { useMembers } from "@/hooks/use-members"
import { GroupRosterEditor } from "./group-roster-editor"
import { GroupRulesEditor, ParentToggle } from "./group-rules-editor"
import type { Group, GroupType, RuleLogic } from "@/types/api"

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
  const { data: manualRows = [] } = useGroupManualMembers(id)
  const { data: allMembers = [] } = useMembers()

  const updateGroup = useUpdateGroup()

  const [name, setName] = useState(group.name)
  const [type, setType] = useState<GroupType>(group.group_type)
  const [color, setColor] = useState(group.color ?? PRESET_COLORS[0].hex)
  const [description, setDescription] = useState(group.description ?? "")
  const [ruleLogic, setRuleLogic] = useState<RuleLogic>(group.rule_logic)
  const [includeParents, setIncludeParents] = useState(group.include_parents)
  const [ccParents, setCcParents] = useState(group.cc_parents_on_messages)
  const [nameError, setNameError] = useState<string | null>(null)

  const isSystem = group.is_system
  const manualIds = new Set(manualRows.map((r) => r.member_id))

  async function handleSave() {
    if (!name.trim()) { setNameError("Name is required."); return }
    setNameError(null)
    updateGroup.mutate(
      { id, data: { name: name.trim(), group_type: type, color, description: description.trim() || null, rule_logic: ruleLogic, include_parents: includeParents, cc_parents_on_messages: ccParents } },
      {
        onSuccess: () => router.push("/groups"),
        onError: (err) => {
          setNameError(apiErrorMessage(err, { 409: "A group with this name already exists." }))
        },
      },
    )
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
        <GroupRosterEditor
          group={group}
          type={type}
          members={members}
          manualMemberIds={manualIds}
          allMembers={allMembers}
        />

        {/* ── Dynamic Rules (custom only) ─────────────────── */}
        {type === "custom" && (
          <>
            <Separator />
            <GroupRulesEditor
              group={group}
              ruleLogic={ruleLogic}
              onRuleLogicChange={setRuleLogic}
            />

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
