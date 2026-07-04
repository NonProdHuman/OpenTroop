import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MetricMeter, metricLabel, rankSummary, statusBadgeVariant } from "./rank-progress"
import type { MemberRankView, MetricProgress } from "@/types/api"

const meter = (overrides: Partial<MetricProgress> = {}): MetricProgress => ({
  kind: "service_hours",
  window: "since_joining",
  threshold: 6,
  value: 2.5,
  met: false,
  ...overrides,
})

describe("metricLabel", () => {
  it("combines kind and window labels", () => {
    expect(metricLabel(meter())).toBe("Service hours (since joining)")
    expect(metricLabel(meter({ window: "any", kind: "merit_badge_count" }))).toBe("Merit badges")
  })

  it("falls back to raw values for unknown kinds", () => {
    expect(metricLabel(meter({ kind: "mystery_metric", window: "any" }))).toBe("mystery_metric")
  })
})

describe("statusBadgeVariant", () => {
  it("maps each workflow status", () => {
    expect(statusBadgeVariant("approved")).toBe("default")
    expect(statusBadgeVariant("reported")).toBe("secondary")
    expect(statusBadgeVariant("rejected")).toBe("destructive")
  })
})

describe("rankSummary", () => {
  it("counts only top-level requirements", () => {
    const view = {
      requirements: [
        { requirement: { parent_id: null }, is_complete: true },
        { requirement: { parent_id: null }, is_complete: false },
        { requirement: { parent_id: "parent" }, is_complete: true },
      ],
    } as unknown as MemberRankView
    expect(rankSummary(view)).toEqual({ complete: 1, total: 2 })
  })
})

describe("MetricMeter", () => {
  it("renders value over threshold", () => {
    render(<MetricMeter metric={meter({ value: 2.5 })} />)
    expect(screen.getByText("2.5 / 6")).toBeInTheDocument()
  })

  it("explains an unavailable window anchor instead of showing zero", () => {
    render(<MetricMeter metric={meter({ value: null, window: "since_rank" })} />)
    expect(screen.getByText("awaiting previous rank date")).toBeInTheDocument()
  })
})
