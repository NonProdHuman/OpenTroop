import type { EventType } from "@/types/api"

/** A small pill showing an event type's name with its color dot. */
export function EventTypeBadge({ type }: { type: Pick<EventType, "name" | "color"> }) {
  const color = type.color ?? "#6b7280"
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium">
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      {type.name}
    </span>
  )
}
