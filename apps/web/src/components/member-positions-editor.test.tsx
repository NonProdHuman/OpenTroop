/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemberPositionsEditor } from "./member-positions-editor"
import * as memberPositionsHook from "@/hooks/use-member-positions"
import type { MemberPositionAssignment, Position } from "@/types/api"

vi.mock("@/hooks/use-member-positions", () => ({
  useAssignMemberPosition: vi.fn(),
  useRemoveMemberPosition: vi.fn(),
}))

// Render Popover inline so the combobox is always visible
vi.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: any) => <div>{children}</div>,
  PopoverTrigger: ({ children, ...props }: any) => (
    <button type="button" {...props}>{children}</button>
  ),
  PopoverContent: ({ children }: any) => (
    <div data-testid="popover-content">{children}</div>
  ),
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
  ...overrides,
})

const makeAssignment = (overrides: Partial<MemberPositionAssignment>): MemberPositionAssignment => ({
  id: "a1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  member_id: "m1",
  position_id: "p1",
  assigned_by_id: null,
  ...overrides,
})

describe("MemberPositionsEditor", () => {
  const mockAssign = vi.fn()
  const mockRemove = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(memberPositionsHook.useAssignMemberPosition).mockReturnValue({
      mutate: mockAssign,
      isPending: false,
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

  it("shows 'No positions assigned' when there are no assignments", () => {
    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[makePosition({})]}
        canAssign={false}
      />
    )
    expect(screen.getByText("No positions assigned")).toBeInTheDocument()
  })

  it("renders existing position badges", () => {
    const position = makePosition({ id: "p1", name: "Patrol Leader" })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[position]}
        canAssign={false}
      />
    )
    expect(screen.getByText("Patrol Leader")).toBeInTheDocument()
  })

  it("hides the remove button when canAssign is false", () => {
    const position = makePosition({ id: "p1", name: "Patrol Leader", is_system: false })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[position]}
        canAssign={false}
      />
    )
    expect(screen.queryByRole("button", { name: /remove patrol leader/i })).not.toBeInTheDocument()
  })

  it("shows the remove button for non-system positions when canAssign is true", () => {
    const position = makePosition({ id: "p1", name: "Patrol Leader", is_system: false })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[position]}
        canAssign={true}
      />
    )
    expect(screen.getByRole("button", { name: /remove patrol leader/i })).toBeInTheDocument()
  })

  it("hides the remove button for system positions even when canAssign is true", () => {
    const position = makePosition({ id: "p1", name: "Scoutmaster", is_system: true })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[position]}
        canAssign={true}
      />
    )
    expect(screen.queryByRole("button", { name: /remove scoutmaster/i })).not.toBeInTheDocument()
  })

  it("calls removePosition mutation when remove button is clicked", async () => {
    const position = makePosition({ id: "p1", name: "Patrol Leader", is_system: false })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[position]}
        canAssign={true}
      />
    )

    await userEvent.click(screen.getByRole("button", { name: /remove patrol leader/i }))
    expect(mockRemove).toHaveBeenCalledWith({ memberId: "m1", positionId: "p1" })
  })

  it("shows 'Add position' combobox when canAssign is true and unassigned positions exist", () => {
    const position = makePosition({ id: "p1", name: "Patrol Leader" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[position]}
        canAssign={true}
      />
    )
    // The trigger text is visible; we can't use role="combobox" alone because the
    // inline-rendered CommandInput also carries that role in the mock environment.
    expect(screen.getByText(/add position/i)).toBeInTheDocument()
  })

  it("hides the combobox when canAssign is false", () => {
    const position = makePosition({})

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[position]}
        canAssign={false}
      />
    )
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
  })

  it("shows note when canAssign is true but no positions have been created", () => {
    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[]}
        canAssign={true}
      />
    )
    expect(screen.getByText(/no positions have been created yet/i)).toBeInTheDocument()
  })

  it("calls assignPosition mutation when a position is selected from the combobox", async () => {
    const position = makePosition({ id: "p2", name: "Assistant Patrol Leader" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[]}
        allPositions={[position]}
        canAssign={true}
      />
    )

    const popoverContent = screen.getByTestId("popover-content")
    const option = within(popoverContent).getByText("Assistant Patrol Leader")
    await userEvent.click(option)

    expect(mockAssign).toHaveBeenCalledWith({ memberId: "m1", positionId: "p2" })
  })

  it("excludes already-assigned positions from the add combobox", () => {
    const p1 = makePosition({ id: "p1", name: "Patrol Leader" })
    const p2 = makePosition({ id: "p2", name: "Assistant Patrol Leader" })
    const assignment = makeAssignment({ position_id: "p1" })

    render(
      <MemberPositionsEditor
        memberId="m1"
        assignments={[assignment]}
        allPositions={[p1, p2]}
        canAssign={true}
      />
    )

    const popoverContent = screen.getByTestId("popover-content")
    expect(within(popoverContent).queryByText("Patrol Leader")).not.toBeInTheDocument()
    expect(within(popoverContent).getByText("Assistant Patrol Leader")).toBeInTheDocument()
  })
})
