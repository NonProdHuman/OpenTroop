import { describe, expect, it } from "vitest"
import { formatMemberName, splitEventsByTime } from "./format"

describe("formatMemberName", () => {
  it("includes the nickname when present", () => {
    expect(formatMemberName({ first_name: "Sam", last_name: "Scout", nickname: "Sammy" })).toBe(
      'Sam "Sammy" Scout',
    )
    expect(formatMemberName({ first_name: "Sam", last_name: "Scout", nickname: null })).toBe(
      "Sam Scout",
    )
  })
})

describe("splitEventsByTime", () => {
  const now = new Date("2026-07-04T12:00:00Z")
  const event = (start: string) => ({ scheduled_start: start })

  it("splits and orders upcoming ascending, past descending", () => {
    const { upcoming, past } = splitEventsByTime(
      [
        event("2026-07-10T09:00:00Z"),
        event("2026-06-01T09:00:00Z"),
        event("2026-07-05T09:00:00Z"),
        event("2026-07-01T09:00:00Z"),
      ],
      now,
    )
    expect(upcoming.map((e) => e.scheduled_start)).toEqual([
      "2026-07-05T09:00:00Z",
      "2026-07-10T09:00:00Z",
    ])
    expect(past.map((e) => e.scheduled_start)).toEqual([
      "2026-07-01T09:00:00Z",
      "2026-06-01T09:00:00Z",
    ])
  })

  it("counts an event starting exactly now as upcoming", () => {
    const { upcoming, past } = splitEventsByTime([event("2026-07-04T12:00:00Z")], now)
    expect(upcoming).toHaveLength(1)
    expect(past).toHaveLength(0)
  })
})
