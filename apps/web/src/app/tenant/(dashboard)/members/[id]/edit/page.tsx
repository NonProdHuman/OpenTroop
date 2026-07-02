"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useMember, useMembers, useUpdateMember } from "@/hooks/use-members"
import { useGroups, useMemberGroups } from "@/hooks/use-groups"
import { useMemberPositions } from "@/hooks/use-member-positions"
import { usePositions } from "@/hooks/use-positions"
import { usePermissions } from "@/hooks/use-session"
import { FamilyRelationshipsEditor } from "@/components/family-relationships-editor"
import { GroupMembershipEditor } from "@/components/group-membership-editor"
import { MemberPositionsEditor } from "@/components/member-positions-editor"
import { PageHeader } from "@/components/page-header"
import { FormField, SectionTitle } from "@/components/form-helpers"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { useRelationships } from "@/hooks/use-relationships"
import type { Member } from "@/types/api"
import {
  MemberFormFields,
  toApiPayload,
  toFormState,
  type MemberFormState,
} from "../../member-form"

export default function MemberEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: member, isLoading } = useMember(id)

  if (isLoading || !member) {
    return (
      <div className="p-6 text-muted-foreground text-sm">Loading…</div>
    )
  }

  return <MemberEditForm id={id} member={member} />
}

function MemberEditForm({ id, member }: { id: string; member: Member }) {
  const router = useRouter()
  const { has } = usePermissions()
  const canFullEdit = has("member:write")
  const { data: groups = [] } = useGroups()
  const memberGroups = useMemberGroups(id)
  const { data: assignments = [] } = useMemberPositions(id)
  const { data: allPositions = [] } = usePositions()
  const { data: relationships = [] } = useRelationships(id)
  const { data: allMembers = [] } = useMembers()
  const updateMember = useUpdateMember()

  const [form, setForm] = useState<MemberFormState>(() => toFormState(member))
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof MemberFormState>(key: K, value: MemberFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSave() {
    if (!form.first_name.trim() || !form.last_name.trim()) {
      setError("First name and last name are required.")
      return
    }
    setError(null)
    updateMember.mutate(
      { id, data: toApiPayload(form, canFullEdit) },
      { onSuccess: () => router.push("/members") },
    )
  }

  const displayName = `${member.first_name} ${member.last_name}`

  return (
    <>
      <PageHeader title={`Edit — ${displayName}`}>
        <Button variant="outline" onClick={() => router.push("/members")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updateMember.isPending}>
          {updateMember.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-2xl mx-auto p-4 md:p-6 space-y-6">
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {updateMember.isError && (
          <p className="text-sm text-destructive">
            Save failed — please try again.
          </p>
        )}

        <MemberFormFields form={form} set={set} canFullEdit={canFullEdit} />

        <Separator />

        {/* ── Family ───────────────────────────────────────── */}
        <SectionTitle>Family</SectionTitle>
        <FamilyRelationshipsEditor
          memberId={id}
          relationships={relationships}
          allMembers={allMembers}
        />

        <Separator />

        {/* ── Groups & Patrols ─────────────────────────────── */}
        <SectionTitle>Groups &amp; Patrols</SectionTitle>
        <GroupMembershipEditor
          memberId={id}
          memberGroups={memberGroups}
          allGroups={groups}
        />

        <Separator />

        {/* ── Positions ────────────────────────────────────── */}
        <SectionTitle>Positions</SectionTitle>
        <MemberPositionsEditor
          memberId={id}
          assignments={assignments}
          allPositions={allPositions}
          canAssign={has("role:assign")}
        />

        <Separator />

        {/* ── Notes ────────────────────────────────────────── */}
        <SectionTitle>Notes</SectionTitle>
        <FormField label="Internal notes">
          <Textarea
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
            rows={3}
            disabled={!canFullEdit}
          />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/members")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateMember.isPending}>
            {updateMember.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </>
  )
}
