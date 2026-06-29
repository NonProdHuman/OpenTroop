"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCreatePosition } from "@/hooks/use-positions"
import type { PositionScope } from "@/types/api"

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}

function FormField({
  label,
  children,
  required,
}: {
  label: string
  children: React.ReactNode
  required?: boolean
}) {
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

export default function NewPositionPage() {
  const router = useRouter()
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [slugEdited, setSlugEdited] = useState(false)
  const [appliesTo, setAppliesTo] = useState<PositionScope>("any")
  const [sortOrder, setSortOrder] = useState("0")
  const [error, setError] = useState<string | null>(null)

  const createPosition = useCreatePosition()

  function handleNameChange(v: string) {
    setName(v)
    if (!slugEdited) setSlug(slugify(v))
  }

  async function handleSave() {
    if (!name.trim()) { setError("Name is required."); return }
    if (!slug.trim()) { setError("Slug is required."); return }
    setError(null)
    createPosition.mutate(
      {
        name: name.trim(),
        slug: slug.trim(),
        applies_to: appliesTo,
        sort_order: parseInt(sortOrder, 10) || 0,
      },
      {
        onSuccess: () => router.push("/positions"),
        onError: (err) => {
          const msg = err instanceof Error ? err.message : ""
          if (msg.includes("409")) setError("A position with this slug already exists.")
          else setError("Something went wrong — please try again.")
        },
      },
    )
  }

  return (
    <>
      <PageHeader title="New Position">
        <Button variant="outline" onClick={() => router.push("/positions")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={createPosition.isPending}>
          {createPosition.isPending ? "Creating…" : "Create position"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-5">
        {error && <p className="text-sm text-destructive">{error}</p>}

        <FormField label="Name" required>
          <Input
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Scoutmaster"
          />
        </FormField>

        <FormField label="Slug" required>
          <Input
            value={slug}
            onChange={(e) => { setSlug(e.target.value); setSlugEdited(true) }}
            placeholder="scoutmaster"
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Unique identifier used in rules and APIs. Auto-generated from name.
          </p>
        </FormField>

        <FormField label="Applies to" required>
          <Select value={appliesTo} onValueChange={(v) => setAppliesTo(v as PositionScope)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any member</SelectItem>
              <SelectItem value="scout">Scouts only</SelectItem>
              <SelectItem value="adult">Adults only</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField label="Sort order">
          <Input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            min={0}
            className="w-24"
          />
          <p className="text-xs text-muted-foreground">
            Lower numbers appear first in lists.
          </p>
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/positions")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={createPosition.isPending}>
            {createPosition.isPending ? "Creating…" : "Create position"}
          </Button>
        </div>
      </div>
    </>
  )
}
