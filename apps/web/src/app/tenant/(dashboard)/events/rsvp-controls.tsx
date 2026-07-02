"use client"

import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
import type { RsvpStatus } from "@/types/api"

/** Shared RSVP input controls for the self-service panel and the leader admin view. */

const STATUS_LABELS: Record<RsvpStatus, string> = {
  no_response: "No response",
  going: "Going",
  declined: "Declined",
  maybe: "Maybe",
}

export function RsvpStatusButtons({
  value,
  onChange,
  disabled,
  labels,
}: {
  value: RsvpStatus
  onChange: (s: RsvpStatus) => void
  disabled?: boolean
  /** Per-status label overrides (e.g. the admin view shows "Clear" for no_response). */
  labels?: Partial<Record<RsvpStatus, string>>
}) {
  const options: RsvpStatus[] = ["going", "declined", "no_response"]
  return (
    <div className="flex gap-1">
      {options.map((s) => (
        <button
          key={s}
          type="button"
          disabled={disabled}
          onClick={() => onChange(s)}
          className={cn(
            "text-xs px-2 py-0.5 rounded-full border transition-colors",
            value === s
              ? s === "going"
                ? "bg-green-600 text-white border-green-600"
                : s === "declined"
                  ? "bg-destructive text-destructive-foreground border-destructive"
                  : "bg-muted border-muted-foreground text-foreground"
              : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
          )}
        >
          {labels?.[s] ?? STATUS_LABELS[s]}
        </button>
      ))}
    </div>
  )
}

export function CheckboxButton({
  checked,
  onToggle,
  disabled,
  size = "md",
  label,
}: {
  checked: boolean
  onToggle: () => void
  disabled?: boolean
  size?: "sm" | "md"
  label: string
}) {
  const box = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"
  const tick = size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        box,
        "rounded border border-border flex items-center justify-center shrink-0",
        checked && "bg-primary border-primary",
      )}
    >
      {checked && <Check className={cn(tick, "text-primary-foreground")} />}
    </button>
  )
}
