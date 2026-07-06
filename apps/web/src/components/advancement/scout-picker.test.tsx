import { describe, expect, it } from "vitest"
import { NO_PATROL_LABEL, groupScoutsByPatrol } from "./scout-picker"
import type { AdvancementScout } from "@/types/api"

const scout = (overrides: Partial<AdvancementScout> = {}): AdvancementScout => ({
  member_id: crypto.randomUUID(),
  first_name: "Sam",
  last_name: "Scout",
  nickname: null,
  membership_status: "active",
  patrol_name: null,
  current_rank_code: null,
  current_rank_name: null,
  ...overrides,
})

describe("groupScoutsByPatrol", () => {
  it("groups by patrol alphabetically with patrol-less scouts trailing", () => {
    const groups = groupScoutsByPatrol([
      scout({ first_name: "NoPatrol" }),
      scout({ first_name: "Wolf1", patrol_name: "Wolves" }),
      scout({ first_name: "Fox1", patrol_name: "Foxes" }),
      scout({ first_name: "Wolf2", patrol_name: "Wolves" }),
    ])
    expect(groups.map((g) => g.patrol)).toEqual(["Foxes", "Wolves", NO_PATROL_LABEL])
    expect(groups[1].scouts.map((s) => s.first_name)).toEqual(["Wolf1", "Wolf2"])
  })

  it("preserves the API's ordering within each group", () => {
    const groups = groupScoutsByPatrol([
      scout({ last_name: "Adams", patrol_name: "Foxes" }),
      scout({ last_name: "Baker", patrol_name: "Foxes" }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].scouts.map((s) => s.last_name)).toEqual(["Adams", "Baker"])
  })

  it("returns an empty list for no scouts", () => {
    expect(groupScoutsByPatrol([])).toEqual([])
  })
})
