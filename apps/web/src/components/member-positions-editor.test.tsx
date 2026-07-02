/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemberPositionsEditor } from "./member-positions-editor"
import * as memberPositionsHook from "@/hooks/use-member-positions"
import type { Member, MemberPositionAssignment, Position } from "@/types/api"

vi.mock("@/hooks/use-member-positions", () => ({
  useAssignMemberPosition: vi.fn(),
  useUpdateMemberPositionTerm: vi.fn(),
  useRemoveMemberPosition: vi.fn(),
}))

// Render Dialog inline (no portal) so dialog content is queryable when open
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ open, children }: any) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h2>{children}</h2>,
  DialogDescription: ({ children }: any) => <p>{children}</p>,
  DialogFooter: ({ children }: any) => <div>{children}</div>,
}))

const makePosition = (overrides: Partial<Position>): Position => ({
  id: "p1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Patrol Leader",
  slug: "patrol-leader",
  applies_to: "scout",
  sort_order: 10,
  is_system: false,
  is_default: false,
  ...overrides,
})

const makeAssignment = (
  overrides: Partial<MemberPositionAssignment>,
): MemberPositionAssignment => ({
  id: "a1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  member_id: "m1",
  position_id: "p1",
  assigned_by_id: null,
  start_date: "2024-01-01",
  end_date: null,
  is_current: true,
  ...overrides,
})

const makeMember = (overrides: Partial<Member>): Member =>
  ({
    id: "m9",
    first_name: "Sarah",
    last_name: "Leader",
    ...overrides,
  }) as Member

async function openHistory() {
  await userEvent.click(screen.getByRole("button", { name: /position history/i }))
  return screen.getByRole("table")
}

describe("MemberPositionsEditor", () => {
  const mockAssign = vi.fn()
  const mockUpdate = vi.fn()
  const mockRemove = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(memberPositionsHook.useAssignMemberPosition).mockReturnValue({
      mutate: mockAssign,
      isPending: false,
      isError: false,
    } as any)
    vi.mocked(memberPositionsHook.useUpdateMemberPositionTerm).mockReturnValue({
      mutate: mockUpdate,
      isPending: false,
      isError: false,
    } as any)
    vi.mocked(memberPositionsHook.useRemoveMemberPosition).mockReturnValue({
      mutate: mockRemove,
      isPending: false,
    } as any)

    class MockResizeObserver {
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = vi.fn()
    }
    vi.stubGlobal("ResizeObserver", MockResizeObserver)
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  it("shows 'No current positions' when there are no assignments", () => {
    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[makePosition({})]}
        canAssign={false}
      />,
    )
    expect(screen.getByText("No current positions")).toBeInTheDocument()
  })

  it("renders badges only for current terms", () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const p2 = makePosition({ id: "p2", name: "Scribe" })
    const current = makeAssignment({ id: "a1", position_id: "p1", is_current: true })
    const ended = makeAssignment({
      id: "a2",
      position_id: "p2",
      start_date: "2023-01-01",
      end_date: "2023-12-31",
      is_current: false,
    })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[current, ended]}
        allPositions={[p1, p2]}
        canAssign={false}
      />,
    )
    expect(screen.getByText("Patrol Leader")).toBeInTheDocument()
    // Ended term appears only in history, which is collapsed by default.
    expect(screen.queryByText("Scribe")).not.toBeInTheDocument()
  })

  it("excludes default positions from badges and history", () => {
    const def = makePosition({ id: "pd", name: "Member", is_default: true })
    const assignment = makeAssignment({ position_id: "pd" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[def]}
        canAssign={false}
      />,
    )
    expect(screen.getByText("No current positions")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /position history/i })).not.toBeInTheDocument()
  })

  it("reveals the history table sorted current-first then start desc", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const p2 = makePosition({ id: "p2", name: "Scribe" })
    const olderEnded = makeAssignment({
      id: "a1",
      position_id: "p2",
      start_date: "2022-01-01",
      end_date: "2022-12-31",
      is_current: false,
    })
    const newerEnded = makeAssignment({
      id: "a2",
      position_id: "p2",
      start_date: "2023-06-01",
      end_date: "2023-12-31",
      is_current: false,
    })
    const current = makeAssignment({
      id: "a3",
      position_id: "p1",
      start_date: "2024-01-01",
      is_current: true,
    })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[olderEnded, current, newerEnded]}
        allPositions={[p1, p2]}
        canAssign={false}
      />,
    )

    const table = await openHistory()
    const rows = within(table).getAllByRole("row").slice(1) // skip header
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent("Patrol Leader")
    expect(rows[0]).toHaveTextContent("Current")
    expect(rows[1]).toHaveTextContent("Jun 1, 2023")
    expect(rows[2]).toHaveTextContent("Jan 1, 2022")
  })

  it("renders 'Present' for an open end date and '—' for an unknown start", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const current = makeAssignment({ id: "a1", position_id: "p1", start_date: null })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[current]}
        allPositions={[p1]}
        canAssign={false}
      />,
    )

    const table = await openHistory()
    const cells = within(table).getAllByRole("cell")
    expect(cells[1]).toHaveTextContent("—") // start
    expect(cells[2]).toHaveTextContent("Present") // end
  })

  it("shows the assigner's name, or '—' when unknown", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const p2 = makePosition({ id: "p2", name: "Scribe" })
    const byKnown = makeAssignment({ id: "a1", position_id: "p1", assigned_by_id: "m9" })
    const byNull = makeAssignment({
      id: "a2",
      position_id: "p2",
      assigned_by_id: null,
      start_date: "2023-01-01",
      end_date: "2023-06-30",
      is_current: false,
    })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[byKnown, byNull]}
        allPositions={[p1, p2]}
        allMembers={[makeMember({ id: "m9" })]}
        canAssign={false}
      />,
    )

    const table = await openHistory()
    const rows = within(table).getAllByRole("row").slice(1)
    expect(rows[0]).toHaveTextContent("Sarah Leader")
    expect(within(rows[1]).getAllByRole("cell")[3]).toHaveTextContent("—")
  })

  it("hides all mutating controls when canAssign is false", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[p1]}
        canAssign={false}
      />,
    )

    expect(screen.queryByRole("button", { name: /add position/i })).not.toBeInTheDocument()
    await openHistory()
    expect(screen.queryByRole("button", { name: /end .* term/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /edit .* term dates/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /delete .* term/i })).not.toBeInTheDocument()
  })

  it("ends a current term today via the end-term button", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const assignment = makeAssignment({ id: "a1", position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[p1]}
        canAssign={true}
      />,
    )

    await openHistory()
    await userEvent.click(screen.getByRole("button", { name: /end patrol leader term/i }))
    expect(mockUpdate).toHaveBeenCalledWith({
      memberId: "m1",
      assignmentId: "a1",
      data: { end_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) },
    })
  })

  it("does not offer end-term on an already-ended term", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const ended = makeAssignment({
      id: "a1",
      position_id: "p1",
      start_date: "2023-01-01",
      end_date: "2023-12-31",
      is_current: false,
    })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[ended]}
        allPositions={[p1]}
        canAssign={true}
      />,
    )

    await openHistory()
    expect(screen.queryByRole("button", { name: /end patrol leader term/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /edit patrol leader term dates/i })).toBeInTheDocument()
  })

  it("soft-deletes a term via the delete button", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const assignment = makeAssignment({ id: "a1", position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[p1]}
        canAssign={true}
      />,
    )

    await openHistory()
    await userEvent.click(screen.getByRole("button", { name: /delete patrol leader term/i }))
    expect(mockRemove).toHaveBeenCalledWith({ memberId: "m1", assignmentId: "a1" })
  })

  it("edits term dates through the edit dialog", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const assignment = makeAssignment({ id: "a1", position_id: "p1", start_date: "2024-01-01" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[p1]}
        canAssign={true}
      />,
    )

    await openHistory()
    await userEvent.click(screen.getByRole("button", { name: /edit patrol leader term dates/i }))

    const dialog = screen.getByTestId("dialog-content")
    fireEvent.change(within(dialog).getByLabelText("End date"), {
      target: { value: "2024-06-30" },
    })
    await userEvent.click(within(dialog).getByRole("button", { name: /save dates/i }))

    expect(mockUpdate).toHaveBeenCalledWith(
      {
        memberId: "m1",
        assignmentId: "a1",
        data: { start_date: "2024-01-01", end_date: "2024-06-30" },
      },
      expect.anything(),
    )
  })

  it("adds a position with dates through the add dialog", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[p1]}
        canAssign={true}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: /add position/i }))
    const dialog = screen.getByTestId("dialog-content")
    await userEvent.click(within(dialog).getByText("Patrol Leader"))
    fireEvent.change(within(dialog).getByLabelText("Start date"), {
      target: { value: "2024-03-01" },
    })
    await userEvent.click(within(dialog).getByRole("button", { name: /^add position$/i }))

    expect(mockAssign).toHaveBeenCalledWith(
      { memberId: "m1", positionId: "p1", startDate: "2024-03-01", endDate: null },
      expect.anything(),
    )
  })

  it("excludes currently-held positions from the add dialog but allows re-adding ended ones", async () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const p2 = makePosition({ id: "p2", name: "Scribe" })
    const current = makeAssignment({ id: "a1", position_id: "p1", is_current: true })
    const ended = makeAssignment({
      id: "a2",
      position_id: "p2",
      start_date: "2023-01-01",
      end_date: "2023-12-31",
      is_current: false,
    })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[current, ended]}
        allPositions={[p1, p2]}
        canAssign={true}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: /add position/i }))
    const dialog = screen.getByTestId("dialog-content")
    expect(within(dialog).queryByText("Patrol Leader")).not.toBeInTheDocument()
    expect(within(dialog).getByText("Scribe")).toBeInTheDocument()
  })

  it("shows note when canAssign is true but no positions have been created", () => {
    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[]}
        canAssign={true}
      />,
    )
    expect(screen.getByText(/no positions have been created yet/i)).toBeInTheDocument()
  })
})
