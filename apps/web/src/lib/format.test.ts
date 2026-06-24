import { describe, expect, it } from "vitest"
import { formatEventWhen, formatMoney } from "./format"

describe("formatMoney", () => {
  it("formats decimal strings as USD", () => {
    expect(formatMoney("25.00")).toBe("$25.00")
    expect(formatMoney("25.5")).toBe("$25.50")
    expect(formatMoney(30)).toBe("$30.00")
  })

  it("returns null for empty/invalid input", () => {
    expect(formatMoney(null)).toBeNull()
    expect(formatMoney(undefined)).toBeNull()
    expect(formatMoney("")).toBeNull()
    expect(formatMoney("abc")).toBeNull()
  })
})

describe("formatEventWhen", () => {
  it("renders a time range for a single-day timed event", () => {
    // Range output contains an en dash regardless of local timezone.
    const out = formatEventWhen("2026-07-10T14:00:00Z", "2026-07-10T17:00:00Z")
    expect(out).toContain("–")
    expect(out).toContain("2026")
  })

  it("collapses a same-day all-day event to one date with no time range", () => {
    const out = formatEventWhen("2026-07-10T12:00:00Z", "2026-07-10T12:00:00Z", true)
    expect(out).not.toContain("–")
    expect(out).toContain("2026")
  })

  it("shows a date range for a multi-day all-day event", () => {
    const out = formatEventWhen("2026-07-10T12:00:00Z", "2026-07-12T12:00:00Z", true)
    expect(out).toContain("–")
  })
})
