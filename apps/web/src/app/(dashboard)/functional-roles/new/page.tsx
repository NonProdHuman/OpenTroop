"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCreateFunctionalRole } from "@/hooks/use-functional-roles"

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}

function FormField({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  )
}

export default function NewFunctionalRolePage() {
  const router = useRouter()
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [slugEdited, setSlugEdited] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createRole = useCreateFunctionalRole()

  function handleNameChange(v: string) {
    setName(v)
    if (!slugEdited) setSlug(slugify(v))
  }

  async function handleSave() {
    if (!name.trim()) { setError("Name is required."); return }
    if (!slug.trim()) { setError("Slug is required."); return }
    setError(null)
    createRole.mutate(
      { name: name.trim(), slug: slug.trim() },
      {
        onSuccess: () => router.push("/functional-roles"),
        onError: (err) => {
          const msg = err instanceof Error ? err.message : ""
          if (msg.includes("409")) setError("A functional role with this slug already exists.")
          else setError("Something went wrong — please try again.")
        },
      },
    )
  }

  return (
    <>
      <PageHeader title="New Functional Role">
        <Button variant="outline" onClick={() => router.push("/functional-roles")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={createRole.isPending}>
          {createRole.isPending ? "Creating…" : "Create role"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-5">
        {error && <p className="text-sm text-destructive">{error}</p>}

        <FormField label="Name" required>
          <Input
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Event Admins"
          />
        </FormField>

        <FormField label="Slug" required>
          <Input
            value={slug}
            onChange={(e) => { setSlug(e.target.value); setSlugEdited(true) }}
            placeholder="event-admins"
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Unique identifier. Auto-generated from name.
          </p>
        </FormField>

        <p className="text-xs text-muted-foreground border-l-2 pl-3">
          After creating the role, open it to add permissions.
          Then link it to positions from the Positions screen.
        </p>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/functional-roles")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={createRole.isPending}>
            {createRole.isPending ? "Creating…" : "Create role"}
          </Button>
        </div>
      </div>
    </>
  )
}
