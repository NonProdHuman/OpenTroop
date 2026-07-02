import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { GroupRulesEditor } from "./group-rules-editor"
import type { Group, GroupRule } from "@/types/api"

const upsertMutate = vi.fn()
const deleteMutate = vi.fn()

let rules: Partial<GroupRule>[] = []

vi.mock("@/hooks/use-groups", () => ({
  useGroupRules: () => ({ data: rules }),
  useGroups: () => ({ data: [] }),
  useUpsertGroupRule: () => ({ mutate: upsertMutate }),
  useDeleteGroupRule: () => ({ mutate: deleteMutate }),
}))

vi.mock("@/hooks/use-positions", () => ({
  usePositions: () => ({ data: [] }),
}))

const group = { id: "g1" } as Group

function renderEditor() {
  return render(<GroupRulesEditor group={group} ruleLogic="and" onRuleLogicChange={() => {}} />)
}

describe("GroupRulesEditor", () => {
  beforeEach(() => {
    upsertMutate.mockReset()
    deleteMutate.mockReset()
    rules = []
  })

  it("shows saved rules as enabled and leaves the rest unchecked", () => {
    rules = [{ id: "r1", dimension: "oa_member", values: null, is_deleted: false }]
    renderEditor()
    expect(screen.getByLabelText(/Only Order of the Arrow Members/)).toBeChecked()
    expect(screen.getByLabelText(/Only Active Order of the Arrow Members/)).not.toBeChecked()
    expect(screen.getByLabelText(/Filter by Member Type/)).not.toBeChecked()
  })

  it("upserts a boolean rule with empty values when toggled on", async () => {
    renderEditor()
    await userEvent.click(screen.getByLabelText(/Only Order of the Arrow Members/))
    expect(upsertMutate).toHaveBeenCalledWith({ groupId: "g1", dimension: "oa_member", values: [] })
  })

  it("deletes a boolean rule when toggled off", async () => {
    rules = [{ id: "r1", dimension: "oa_active", values: null, is_deleted: false }]
    renderEditor()
    await userEvent.click(screen.getByLabelText(/Only Active Order of the Arrow Members/))
    expect(deleteMutate).toHaveBeenCalledWith({ groupId: "g1", dimension: "oa_active" })
  })

  it("expands a value-backed dimension locally without saving, then saves on first value", async () => {
    renderEditor()
    await userEvent.click(screen.getByLabelText(/Filter by Member Type/))
    // Expanding alone must not write anything — there are no values yet.
    expect(upsertMutate).not.toHaveBeenCalled()

    await userEvent.click(screen.getByLabelText("scouts"))
    expect(upsertMutate).toHaveBeenCalledWith({
      groupId: "g1",
      dimension: "member_type",
      values: ["scout"],
    })
  })

  it("adds to the existing values when a second value is checked", async () => {
    rules = [{ id: "r1", dimension: "member_type", values: ["scout"], is_deleted: false }]
    renderEditor()
    await userEvent.click(screen.getByLabelText("adults"))
    expect(upsertMutate).toHaveBeenCalledWith({
      groupId: "g1",
      dimension: "member_type",
      values: ["scout", "adult"],
    })
  })

  it("deletes the rule when the last value is unchecked", async () => {
    rules = [{ id: "r1", dimension: "membership_status", values: ["active"], is_deleted: false }]
    renderEditor()
    await userEvent.click(screen.getByLabelText("active"))
    expect(deleteMutate).toHaveBeenCalledWith({ groupId: "g1", dimension: "membership_status" })
    expect(upsertMutate).not.toHaveBeenCalled()
  })

  it("deletes a saved rule when its dimension is collapsed", async () => {
    rules = [{ id: "r1", dimension: "member_type", values: ["scout"], is_deleted: false }]
    renderEditor()
    await userEvent.click(screen.getByLabelText(/Filter by Member Type/))
    expect(deleteMutate).toHaveBeenCalledWith({ groupId: "g1", dimension: "member_type" })
  })

  it("ignores soft-deleted rules when deriving enabled state", () => {
    rules = [{ id: "r1", dimension: "oa_member", values: null, is_deleted: true }]
    renderEditor()
    expect(screen.getByLabelText(/Only Order of the Arrow Members/)).not.toBeChecked()
  })

  it("keeps the rank dimension disabled (Phase 2)", () => {
    renderEditor()
    expect(screen.getByLabelText(/Filter by Rank/)).toBeDisabled()
  })
})
