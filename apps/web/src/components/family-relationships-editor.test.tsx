/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { FamilyRelationshipsEditor } from "./family-relationships-editor"
import * as relationshipsHook from "@/hooks/use-relationships"
import type { Member, MemberRelationship } from "@/types/api"

vi.mock("@/hooks/use-relationships", () => ({
  useCreateRelationship: vi.fn(),
  useDeleteRelationship: vi.fn(),
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

// Radix Select doesn't work in jsdom — render each option as a plain button that
// fires onValueChange.
const selectState = vi.hoisted(() => ({
  onValueChange: undefined as ((v: string) => void) | undefined,
}))
vi.mock("@/components/ui/select", () => ({
  Select: ({ onValueChange, children }: any) => {
    selectState.onValueChange = onValueChange
    return <div>{children}</div>
  },
  SelectTrigger: ({ children }: any) => <div>{children}</div>,
  SelectValue: () => null,
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ value, children }: any) => (
    <button type="button" onClick={() => selectState.onValueChange?.(value)}>
      {children}
    </button>
  ),
}))

const makeMember = (overrides: Partial<Member>): Member =>
  ({
    id: "m1",
    first_name: "Alice",
    last_name: "Smith",
    member_type: "scout",
    is_deleted: false,
    ...overrides,
  }) as Member

const makeRelationship = (overrides: Partial<MemberRelationship>): MemberRelationship => ({
  id: "r1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  from_member_id: "m1",
  to_member_id: "m2",
  relationship_type: "parent_of",
  ...overrides,
})

describe("FamilyRelationshipsEditor", () => {
  const mockCreate = vi.fn()
  const mockDelete = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(relationshipsHook.useCreateRelationship).mockReturnValue({
      mutate: mockCreate,
      isPending: false,
    } as any)
    vi.mocked(relationshipsHook.useDeleteRelationship).mockReturnValue({
      mutate: mockDelete,
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

  it("shows 'No family relationships' when there are none", () => {
    render(
      <FamilyRelationshipsEditor memberId="m1" relationships={[]} allMembers={[]} />,
    )
    expect(screen.getByText("No family relationships")).toBeInTheDocument()
  })

  it("labels an outgoing parent_of edge from the member's perspective", () => {
    const adult = makeMember({ id: "m1", first_name: "Pat", last_name: "Parent" })
    const child = makeMember({ id: "m2", first_name: "Casey", last_name: "Child" })

    render(
      <FamilyRelationshipsEditor
        memberId="m1"
        relationships={[makeRelationship({ from_member_id: "m1", to_member_id: "m2" })]}
        allMembers={[adult, child]}
      />,
    )
    expect(screen.getByText("Parent / guardian of:")).toBeInTheDocument()
    expect(screen.getByText("Casey Child")).toBeInTheDocument()
  })

  it("flips the label for an incoming parent_of edge", () => {
    const adult = makeMember({ id: "m2", first_name: "Pat", last_name: "Parent" })
    const child = makeMember({ id: "m1", first_name: "Casey", last_name: "Child" })

    render(
      <FamilyRelationshipsEditor
        memberId="m1"
        relationships={[makeRelationship({ from_member_id: "m2", to_member_id: "m1" })]}
        allMembers={[adult, child]}
      />,
    )
    expect(screen.getByText("Child of:")).toBeInTheDocument()
    expect(screen.getByText("Pat Parent")).toBeInTheDocument()
  })

  it("renders '(unknown member)' when the other member isn't loaded", () => {
    render(
      <FamilyRelationshipsEditor
        memberId="m1"
        relationships={[makeRelationship({})]}
        allMembers={[]}
      />,
    )
    expect(screen.getByText("(unknown member)")).toBeInTheDocument()
  })

  it("deletes a relationship from its badge", async () => {
    const other = makeMember({ id: "m2", first_name: "Casey", last_name: "Child" })

    render(
      <FamilyRelationshipsEditor
        memberId="m1"
        relationships={[makeRelationship({ id: "r7" })]}
        allMembers={[other]}
      />,
    )

    await userEvent.click(
      screen.getByRole("button", { name: /remove relationship with casey child/i }),
    )
    expect(mockDelete).toHaveBeenCalledWith({ relId: "r7", memberId: "m1" })
  })

  it("excludes self and already-linked members from the add list", () => {
    const self = makeMember({ id: "m1" })
    const linked = makeMember({ id: "m2", first_name: "Casey", last_name: "Child" })
    const available = makeMember({ id: "m3", first_name: "Bob", last_name: "New" })

    render(
      <FamilyRelationshipsEditor
        memberId="m1"
        relationships={[makeRelationship({})]}
        allMembers={[self, linked, available]}
      />,
    )

    const popover = screen.getByTestId("popover-content")
    expect(within(popover).queryByText("Alice Smith")).not.toBeInTheDocument()
    expect(within(popover).queryByText("Casey Child")).not.toBeInTheDocument()
    expect(within(popover).getByText("Bob New")).toBeInTheDocument()
  })

  it("creates a directional parent_of relationship from this member", async () => {
    const other = makeMember({ id: "m2", first_name: "Casey", last_name: "Child" })

    render(
      <FamilyRelationshipsEditor memberId="m1" relationships={[]} allMembers={[other]} />,
    )

    const popover = screen.getByTestId("popover-content")
    await userEvent.click(within(popover).getByText("Casey Child"))
    expect(mockCreate).toHaveBeenCalledWith({
      from_member_id: "m1",
      to_member_id: "m2",
      relationship_type: "parent_of",
    })
  })

  it("stores sibling_of with the lower id as from_member", async () => {
    // memberId "m2" > other "m1" — the symmetric convention flips the direction.
    const other = makeMember({ id: "m1", first_name: "Bob", last_name: "New" })

    render(
      <FamilyRelationshipsEditor memberId="m2" relationships={[]} allMembers={[other]} />,
    )

    await userEvent.click(screen.getByRole("button", { name: "Sibling of" }))
    const popover = screen.getByTestId("popover-content")
    await userEvent.click(within(popover).getByText("Bob New"))

    expect(mockCreate).toHaveBeenCalledWith({
      from_member_id: "m1",
      to_member_id: "m2",
      relationship_type: "sibling_of",
    })
  })
})
