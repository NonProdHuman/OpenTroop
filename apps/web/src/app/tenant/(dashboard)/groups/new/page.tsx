"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { ColorPicker, PRESET_COLORS } from "@/components/color-picker"
import { FormField } from "@/components/form-helpers"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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

const TYPE_DESCRIPTIONS: Record<string, string> = {
  patrol: "A BSA patrol — scouts belong to at most one patrol. Manual membership only.",
  custom: "A general group — add members by hand and/or with dynamic rules. Configure rules after creating.",
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
      { name: name.trim(), group_type: type, color, description: description.trim() || null, rule_logic: "or" },
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
