import type { Event } from "@/types/api"

export interface DayCell {
  date: Date
  /** Stable "YYYY-M-D" (local) key for this day. */
  key: string
  /** Whether this day belongs to the month being displayed (vs. leading/trailing). */
  inMonth: boolean
  isToday: boolean
}

/** Stable local-date key (ignores time + timezone offset issues across renders). */
export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

/** First day of the month containing `d`, at local midnight. */
export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

/** Add `n` months to `d`, returning the first of that month. */
export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1)
}

/**
 * Build a fixed 6×7 month grid (Sunday-first) for the month containing `month`.
 * Always 6 weeks so the layout height is stable as you navigate.
 */
export function buildMonthGrid(month: Date, today: Date = new Date()): DayCell[][] {
  const first = startOfMonth(month)
  const gridStart = new Date(first.getFullYear(), first.getMonth(), 1 - first.getDay())
  const todayKey = dayKey(today)
  const displayMonth = month.getMonth()

  const weeks: DayCell[][] = []
  for (let w = 0; w < 6; w++) {
    const week: DayCell[] = []
    for (let d = 0; d < 7; d++) {
      const date = new Date(
        gridStart.getFullYear(),
        gridStart.getMonth(),
        gridStart.getDate() + w * 7 + d,
      )
      week.push({
        date,
        key: dayKey(date),
        inMonth: date.getMonth() === displayMonth,
        isToday: dayKey(date) === todayKey,
      })
    }
    weeks.push(week)
  }
  return weeks
}

/**
 * Map each local day key to the events occurring on it. Multi-day events appear
 * on every day they span. Timed events bucket by local calendar date; all-day
 * events bucket by their UTC date so they stay on the intended day regardless of
 * the viewer's timezone. Capped to avoid runaway iteration on malformed ranges.
 */
export function eventsByDay(events: Event[]): Map<string, Event[]> {
  const map = new Map<string, Event[]>()
  for (const e of events) {
    const start = new Date(e.scheduled_start)
    if (Number.isNaN(start.getTime())) continue
    const endRaw = new Date(e.scheduled_end)
    const end = Number.isNaN(endRaw.getTime()) ? start : endRaw

    // For all-day events read the date from the UTC instant; dayKey then formats
    // those numbers into the same "YYYY-M-D" string the (local) grid cells use.
    const cursor = e.all_day
      ? new Date(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate())
      : new Date(start.getFullYear(), start.getMonth(), start.getDate())
    const last = e.all_day
      ? new Date(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate())
      : new Date(end.getFullYear(), end.getMonth(), end.getDate())
    for (let guard = 0; cursor <= last && guard < 366; guard++) {
      const key = dayKey(cursor)
      const bucket = map.get(key)
      if (bucket) bucket.push(e)
      else map.set(key, [e])
      cursor.setDate(cursor.getDate() + 1)
    }
  }
  return map
}
