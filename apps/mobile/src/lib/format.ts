/** Pure display helpers (unit-tested in Node — keep this file free of RN imports). */

export function formatMemberName(m: {
  first_name: string
  last_name: string
  nickname?: string | null
}): string {
  return m.nickname
    ? `${m.first_name} "${m.nickname}" ${m.last_name}`
    : `${m.first_name} ${m.last_name}`
}

/** "Fri, Jul 10 · 9:00 AM" (device locale decides the exact rendering). */
export function formatEventStart(iso: string, allDay: boolean): string {
  const date = new Date(iso)
  const day = date.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  })
  if (allDay) return day
  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
  return `${day} · ${time}`
}

/** Group upcoming/past events for the list: upcoming ascending, past descending. */
export function splitEventsByTime<T extends { scheduled_start: string }>(
  events: readonly T[],
  now: Date,
): { upcoming: T[]; past: T[] } {
  const upcoming: T[] = []
  const past: T[] = []
  for (const event of events) {
    if (new Date(event.scheduled_start) >= now) upcoming.push(event)
    else past.push(event)
  }
  upcoming.sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start))
  past.sort((a, b) => b.scheduled_start.localeCompare(a.scheduled_start))
  return { upcoming, past }
}
