"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useCreateMember } from "@/hooks/use-members"
import { PageHeader } from "@/components/page-header"
import { FormField, SectionTitle } from "@/components/form-helpers"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import {
  EMPTY_MEMBER_FORM,
  MemberFormFields,
  toApiPayload,
  type MemberFormState,
} from "../member-form"

export default function NewMemberPage() {
  const router = useRouter()
  const createMember = useCreateMember()

  const [form, setForm] = useState<MemberFormState>(EMPTY_MEMBER_FORM)
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
    createMember.mutate(toApiPayload(form), {
      onSuccess: () => router.push("/members"),
      onError: (err) => {
        const msg = err instanceof Error ? err.message : String(err)
        if (msg.toLowerCase().includes("403")) {
          setError("You don't have permission to add members.")
        } else if (
          msg.toLowerCase().includes("load failed") ||
          msg.toLowerCase().includes("failed to fetch")
        ) {
          setError("Could not reach the backend — is the server running?")
        } else {
          setError("Something went wrong — please try again.")
        }
      },
    })
  }

  return (
    <>
      <PageHeader title="New member">
        <Button variant="outline" onClick={() => router.push("/members")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={createMember.isPending}>
          {createMember.isPending ? "Creating…" : "Create member"}
        </Button>
      </PageHeader>

      <div className="max-w-2xl mx-auto p-4 md:p-6 space-y-6">
        {error && <p className="text-sm text-destructive">{error}</p>}

        <MemberFormFields form={form} set={set} autoFocus />

        <Separator />

        {/* ── Notes ────────────────────────────────────────── */}
        <SectionTitle>Notes</SectionTitle>
        <FormField label="Internal notes">
          <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={3} />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/members")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={createMember.isPending}>
            {createMember.isPending ? "Creating…" : "Create member"}
          </Button>
        </div>
      </div>
    </>
  )
}
