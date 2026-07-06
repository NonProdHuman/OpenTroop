"use client"

import { useState } from "react"
import { FormField } from "@/components/form-helpers"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { EventTypeInput } from "@/hooks/use-events"
import type { EventType } from "@/types/api"

const DEFAULT_COLOR = "#64748b" // slate-500 — a neutral starting swatch

// Capability flags, in display order. `require_permission_slip` is special-cased
// below (only meaningful when signups are allowed — the backend 422s otherwise).
const CAPABILITIES: { key: keyof EventTypeInput; label: string; hint: string }[] = [
  { key: "allow_signups", label: "Allow sign-ups", hint: "Members can RSVP to events of this type." },
  { key: "allow_guests", label: "Allow guests", hint: "RSVPs can bring a guest count." },
  { key: "is_online", label: "Online event", hint: "Collects a video-conference link instead of a location." },
  { key: "tracks_service_hours", label: "Tracks service hours", hint: "Counts toward service-hour totals." },
  { key: "tracks_camping_nights", label: "Tracks camping nights", hint: "Counts toward camping-night totals." },
  { key: "tracks_mileage", label: "Tracks mileage", hint: "Records hiking / driving miles." },
]

export type EventTypeFormValues = Required<Omit<EventTypeInput, "color">> & { color: string | null }

function initialValues(initial?: EventType): EventTypeFormValues {
  return {
    name: initial?.name ?? "",
    color: initial?.color ?? DEFAULT_COLOR,
    is_active: initial?.is_active ?? true,
    is_online: initial?.is_online ?? false,
    allow_guests: initial?.allow_guests ?? false,
    allow_signups: initial?.allow_signups ?? true,
    require_permission_slip: initial?.require_permission_slip ?? false,
    tracks_service_hours: initial?.tracks_service_hours ?? false,
    tracks_camping_nights: initial?.tracks_camping_nights ?? false,
    tracks_mileage: initial?.tracks_mileage ?? false,
  }
}

function Toggle({
  checked,
  disabled,
  onChange,
  label,
  hint,
}: {
  checked: boolean
  disabled?: boolean
  onChange: (v: boolean) => void
  label: string
  hint: string
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-md border p-3 ${disabled ? "opacity-50" : "cursor-pointer hover:bg-muted/40"}`}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 accent-primary"
      />
      <span className="space-y-0.5">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
    </label>
  )
}

export function EventTypeForm({
  title,
  initial,
  submitLabel,
  submitting,
  error,
  onSubmit,
  onCancel,
  onDelete,
  deleting,
  deletable,
}: {
  title: string
  initial?: EventType
  submitLabel: string
  submitting: boolean
  error: string | null
  onSubmit: (values: EventTypeFormValues) => void
  onCancel: () => void
  onDelete?: () => void
  deleting?: boolean
  deletable?: boolean
}) {
  const [values, setValues] = useState<EventTypeFormValues>(() => initialValues(initial))
  const [localError, setLocalError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    onDelete?.()
  }

  function set<K extends keyof EventTypeFormValues>(key: K, value: EventTypeFormValues[K]) {
    setValues((prev) => {
      const next = { ...prev, [key]: value }
      // Permission slips require signups; clear the flag when signups are turned off.
      if (key === "allow_signups" && value === false) next.require_permission_slip = false
      return next
    })
  }

  function handleSubmit() {
    if (!values.name.trim()) {
      setLocalError("Name is required.")
      return
    }
    setLocalError(null)
    onSubmit({ ...values, name: values.name.trim(), color: values.color || null })
  }

  return (
    <>
      <PageHeader title={title}>
        {deletable && onDelete && (
          <Button
            variant={confirmDelete ? "destructive" : "outline"}
            onClick={handleDelete}
            disabled={deleting}
          >
            {confirmDelete ? "Confirm delete" : "Delete"}
          </Button>
        )}
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Saving…" : submitLabel}
        </Button>
      </PageHeader>

      <div className="max-w-lg mx-auto p-4 md:p-6 space-y-5">
        {(localError || error) && <p className="text-sm text-destructive">{localError || error}</p>}

        <FormField label="Name" required>
          <Input
            value={values.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="Campout"
          />
        </FormField>

        <FormField label="Color">
          <div className="flex items-center gap-3">
            <input
              type="color"
              value={values.color ?? DEFAULT_COLOR}
              onChange={(e) => set("color", e.target.value)}
              className="h-9 w-12 cursor-pointer rounded border bg-transparent p-0.5"
              aria-label="Event type color"
            />
            <Input
              value={values.color ?? ""}
              onChange={(e) => set("color", e.target.value)}
              placeholder={DEFAULT_COLOR}
              className="font-mono text-sm w-32"
            />
          </div>
          <p className="text-xs text-muted-foreground">Used for the badge and calendar dots.</p>
        </FormField>

        <div className="space-y-2">
          <p className="text-sm font-medium">Capabilities</p>
          {CAPABILITIES.map((c) => (
            <Toggle
              key={c.key}
              checked={Boolean(values[c.key])}
              onChange={(v) => set(c.key, v)}
              label={c.label}
              hint={c.hint}
            />
          ))}
          <Toggle
            checked={values.require_permission_slip}
            disabled={!values.allow_signups}
            onChange={(v) => set("require_permission_slip", v)}
            label="Require permission slip"
            hint={
              values.allow_signups
                ? "Sign-ups must submit a permission slip."
                : "Enable sign-ups first to require permission slips."
            }
          />
        </div>

        <FormField label="Active">
          <Toggle
            checked={values.is_active}
            onChange={(v) => set("is_active", v)}
            label="Active"
            hint="Inactive types are hidden from new-event pickers and filters."
          />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving…" : submitLabel}
          </Button>
        </div>
      </div>
    </>
  )
}
