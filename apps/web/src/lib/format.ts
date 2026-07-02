export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null
  try {
    return new Date(value + "T00:00:00").toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return value
  }
}

/**
 * Format a UTC ISO datetime for display. Timed values render in the user's
 * local timezone; all-day values pass `utc: true` so the calendar date is read
 * straight from the stored UTC instant and doesn't drift across timezones.
 */
export function formatDateTime(
  value: string,
  opts: { dateOnly?: boolean; utc?: boolean } = {},
): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(opts.dateOnly ? {} : { hour: "numeric", minute: "2-digit" }),
    ...(opts.utc ? { timeZone: "UTC" } : {}),
  })
}

/**
 * Human "when" string for an event. Collapses same-day ranges to a single date
 * with a start–end time; all-day events drop the time entirely.
 */
export function formatEventWhen(start: string, end: string, allDay = false, short = false): string {
  const s = new Date(start)
  const e = new Date(end)
  if (Number.isNaN(s.getTime())) return start
  if (allDay) {
    // All-day events are timezone-stable: read the date from the UTC instant.
    const sd = formatDateTime(start, { dateOnly: true, utc: true })
    const ed = formatDateTime(end, { dateOnly: true, utc: true })
    return sd === ed ? sd : `${sd} – ${ed}`
  }
  const sameDay = s.toDateString() === e.toDateString()
  if (short) {
    const sd = formatDateTime(start, { dateOnly: true })
    const ed = formatDateTime(end, { dateOnly: true })
    return sameDay ? sd : `${sd} – ${ed}`
  }
  if (sameDay && !Number.isNaN(e.getTime())) {
    const time = e.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
    return `${formatDateTime(start)} – ${time}`
  }
  return `${formatDateTime(start)} – ${formatDateTime(end)}`
}

/** Format a Decimal money string (or number) as e.g. "$25.00". Null → null. */
export function formatMoney(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined || value === "") return null
  const n = Number(value)
  if (Number.isNaN(n)) return null
  return `$${n.toFixed(2)}`
}

/**
 * Canonical member display name. Nicknames always render, in quotes
 * ('Robert "Bob" Smith') — decided once here so every screen agrees.
 */
export function formatMemberName(m: {
  first_name: string
  last_name: string
  nickname?: string | null
}): string {
  return m.nickname
    ? `${m.first_name} "${m.nickname}" ${m.last_name}`
    : `${m.first_name} ${m.last_name}`
}
