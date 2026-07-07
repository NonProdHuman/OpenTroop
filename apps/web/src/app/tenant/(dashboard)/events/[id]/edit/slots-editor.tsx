"use client"

import { useState } from "react"
import { Trash2, Pencil, Plus } from "lucide-react"
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
import { SectionTitle } from "@/components/form-helpers"
import { apiErrorMessage } from "@/lib/api"
import { toLocalInput } from "../../event-form"
import {
  useCreateSlot,
  useDeleteSlot,
  useEventSlots,
  useUpdateSlot,
} from "@/hooks/use-event-slots"
import type { EventSlot } from "@/types/api"

type Scope = "any" | "scout" | "adult"

interface DraftState {
  name: string
  description: string
  capacity: string
  applies_to: Scope
  starts_at: string
  ends_at: string
}

const EMPTY_DRAFT: DraftState = {
  name: "",
  description: "",
  capacity: "",
  applies_to: "any",
  starts_at: "",
  ends_at: "",
}

function fromSlot(slot: EventSlot): DraftState {
  return {
    name: slot.name,
    description: slot.description ?? "",
    capacity: slot.capacity === null ? "" : String(slot.capacity),
    applies_to: slot.applies_to,
    starts_at: slot.starts_at ? toLocalInput(new Date(slot.starts_at)) : "",
    ends_at: slot.ends_at ? toLocalInput(new Date(slot.ends_at)) : "",
  }
}

/** Convert the editable draft into the API payload shape (nulls for blanks). */
function toPayload(draft: DraftState) {
  const capacity = draft.capacity.trim() === "" ? null : Number(draft.capacity)
  return {
    name: draft.name.trim(),
    description: draft.description.trim() === "" ? null : draft.description.trim(),
    capacity,
    applies_to: draft.applies_to,
    starts_at: draft.starts_at ? new Date(draft.starts_at).toISOString() : null,
    ends_at: draft.ends_at ? new Date(draft.ends_at).toISOString() : null,
  }
}

function DraftFields({
  draft,
  set,
}: {
  draft: DraftState
  set: <K extends keyof DraftState>(key: K, value: DraftState[K]) => void
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <Input
        placeholder="Slot name (e.g. Driver — to camp)"
        value={draft.name}
        onChange={(e) => set("name", e.target.value)}
        className="sm:col-span-2"
        data-testid="slot-draft-name"
      />
      <Input
        type="number"
        min={1}
        placeholder="Capacity (blank = unlimited)"
        value={draft.capacity}
        onChange={(e) => set("capacity", e.target.value)}
      />
      <Select value={draft.applies_to} onValueChange={(v) => set("applies_to", v as Scope)}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="any">Anyone</SelectItem>
          <SelectItem value="scout">Scouts only</SelectItem>
          <SelectItem value="adult">Adults only</SelectItem>
        </SelectContent>
      </Select>
      <label className="text-xs text-muted-foreground space-y-1">
        <span>Starts (optional)</span>
        <Input
          type="datetime-local"
          value={draft.starts_at}
          onChange={(e) => set("starts_at", e.target.value)}
        />
      </label>
      <label className="text-xs text-muted-foreground space-y-1">
        <span>Ends (optional)</span>
        <Input
          type="datetime-local"
          value={draft.ends_at}
          onChange={(e) => set("ends_at", e.target.value)}
        />
      </label>
      <Textarea
        placeholder="Description (optional)"
        value={draft.description}
        onChange={(e) => set("description", e.target.value)}
        className="sm:col-span-2"
        rows={2}
      />
    </div>
  )
}

function SlotRow({ eventId, slot }: { eventId: string; slot: EventSlot }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<DraftState>(() => fromSlot(slot))
  const [error, setError] = useState<string | null>(null)
  const updateSlot = useUpdateSlot(eventId)
  const deleteSlot = useDeleteSlot(eventId)

  function set<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }

  function handleSave() {
    if (!draft.name.trim()) {
      setError("Name is required.")
      return
    }
    setError(null)
    updateSlot.mutate(
      { slotId: slot.id, data: toPayload(draft) },
      {
        onSuccess: () => setEditing(false),
        onError: (err) => setError(apiErrorMessage(err)),
      },
    )
  }

  const fill =
    slot.capacity === null
      ? `${slot.signups.length} signed up`
      : `${slot.signups.length} of ${slot.capacity}`

  if (editing) {
    return (
      <div className="rounded-lg border border-border p-3 space-y-2">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DraftFields draft={draft} set={set} />
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDraft(fromSlot(slot))
              setError(null)
              setEditing(false)
            }}
          >
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={updateSlot.isPending}>
            Save
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex items-center justify-between gap-2 rounded-lg border border-border p-3"
      data-testid={`slot-row-${slot.id}`}
    >
      <div className="min-w-0">
        <p className="text-sm font-medium truncate">{slot.name}</p>
        <p className="text-xs text-muted-foreground">
          {fill}
          {slot.applies_to !== "any" &&
            ` · ${slot.applies_to === "scout" ? "Scouts only" : "Adults only"}`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setEditing(true)}
          aria-label={`Edit ${slot.name}`}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={deleteSlot.isPending}
          onClick={() => deleteSlot.mutate(slot.id)}
          aria-label={`Delete ${slot.name}`}
          data-testid={`slot-delete-${slot.id}`}
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </Button>
      </div>
    </div>
  )
}

export function SlotsEditor({ eventId }: { eventId: string }) {
  const { data: slots = [] } = useEventSlots(eventId)
  const createSlot = useCreateSlot(eventId)
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT)
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }

  function handleAdd() {
    if (!draft.name.trim()) {
      setError("Name is required.")
      return
    }
    setError(null)
    // New slots append to the end of the manager-controlled order.
    createSlot.mutate(
      { ...toPayload(draft), sort_order: slots.length },
      {
        onSuccess: () => setDraft(EMPTY_DRAFT),
        onError: (err) => setError(apiErrorMessage(err)),
      },
    )
  }

  return (
    <div className="space-y-3" data-testid="slots-editor">
      <SectionTitle>Sign-up slots</SectionTitle>
      <p className="text-xs text-muted-foreground">
        Named roles or shifts members can claim — drivers, grubmaster, cleanup crews.
        Leave capacity blank for unlimited.
      </p>

      <div className="space-y-2">
        {slots.map((slot) => (
          <SlotRow key={slot.id} eventId={eventId} slot={slot} />
        ))}
      </div>

      <div className="rounded-lg border border-dashed border-border p-3 space-y-2">
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DraftFields draft={draft} set={set} />
        <div className="flex justify-end">
          <Button size="sm" onClick={handleAdd} disabled={createSlot.isPending}>
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Add slot
          </Button>
        </div>
      </div>
    </div>
  )
}
