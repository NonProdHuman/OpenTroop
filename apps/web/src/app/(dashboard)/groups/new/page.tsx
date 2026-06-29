"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCreateGroup } from "@/hooks/use-groups"
import type { GroupType } from "@/types/api"

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

const TYPE_DESCRIPTIONS: Record<string, string> = {
  patrol: "A BSA patrol — scouts belong to at most one patrol. Manual membership only.",
  custom: "A general group — add members by hand and/or with dynamic rules. Configure rules after creating.",
}

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
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

export default function NewGroupPage() {
  const router = useRouter()
  const createGroup = useCreateGroup()

  const [name, setName] = useState("")
  const [type, setType] = useState<GroupType>("custom")
  const [color, setColor] = useState(PRESET_COLORS[0].hex)
  const [description, setDescription] = useState("")
  const [nameError, setNameError] = useState<string | null>(null)

  async function handleSave() {
    if (!name.trim()) {
      setNameError("Name is required.")
      return
    }
    setNameError(null)
    createGroup.mutate(
      { name: name.trim(), group_type: type, color, description: description.trim() || null },
      {
        onSuccess: () => router.push("/groups"),
        onError: (err) => {
          console.error("[create group]", err)
          const msg = err instanceof Error ? err.message : String(err)
          if (msg.includes("409")) {
            setNameError("A group with this name already exists.")
          } else if (msg.toLowerCase().includes("load failed") || msg.toLowerCase().includes("failed to fetch")) {
            setNameError("Could not reach the backend — is the server running?")
          } else {
            setNameError(`Error: ${msg}`)
          }
        },
      },
    )
  }

  return (
    <>
      <PageHeader title="New group">
        <Button variant="outline" onClick={() => router.push("/groups")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={createGroup.isPending}>
          {createGroup.isPending ? "Creating…" : "Create group"}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-6">
        <FormField label="Name" required>
          <Input
            value={name}
            onChange={(e) => { setName(e.target.value); setNameError(null) }}
            placeholder="e.g. Eagle Patrol, PLC, SPL Team"
            autoFocus
          />
          {nameError && <p className="text-sm text-destructive mt-1">{nameError}</p>}
        </FormField>

        <FormField label="Type" required>
          <Select value={type} onValueChange={(v) => setType(v as GroupType)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="custom">Custom group</SelectItem>
              <SelectItem value="patrol">Patrol</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground mt-1">{TYPE_DESCRIPTIONS[type]}</p>
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

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/groups")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={createGroup.isPending}>
            {createGroup.isPending ? "Creating…" : "Create group"}
          </Button>
        </div>
      </div>
    </>
  )
}
