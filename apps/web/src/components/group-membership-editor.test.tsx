/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { GroupMembershipEditor } from "./group-membership-editor"
import * as groupsHook from "@/hooks/use-groups"
import type { Group } from "@/types/api"

vi.mock("@/hooks/use-groups", () => ({
  useAddGroupMember: vi.fn(),
  useRemoveGroupMember: vi.fn(),
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

const makeGroup = (overrides: Partial<Group>): Group => ({
  id: "g1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Eagle Patrol",
  description: null,
  group_type: "patrol",
  color: null,
  is_system: false,
  rule_logic: "and",
  include_parents: false,
  cc_parents_on_messages: false,
  ...overrides,
})

describe("GroupMembershipEditor", () => {
  const mockAdd = vi.fn()
  const mockRemove = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(groupsHook.useAddGroupMember).mockReturnValue({
      mutate: mockAdd,
      isPending: false,
    } as any)
    vi.mocked(groupsHook.useRemoveGroupMember).mockReturnValue({
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

  it("shows 'No group memberships' when the member is in no groups", () => {
    render(
      <GroupMembershipEditor memberId="m1" memberGroups={[]} allGroups={[makeGroup({})]} />,
    )
    expect(screen.getByText("No group memberships")).toBeInTheDocument()
  })

  it("sorts patrol bubbles before custom groups", () => {
    const custom = makeGroup({ id: "g1", name: "Alpha Committee", group_type: "custom" })
    const patrol = makeGroup({ id: "g2", name: "Zebra Patrol", group_type: "patrol" })

    render(
      <GroupMembershipEditor
        memberId="m1"
        memberGroups={[custom, patrol]}
        allGroups={[custom, patrol]}
      />,
    )

    const patrolBubble = screen.getByText("Zebra Patrol")
    const customBubble = screen.getByText("Alpha Committee")
    expect(
      patrolBubble.compareDocumentPosition(customBubble) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it("removes a member from a non-system group", async () => {
    const group = makeGroup({ id: "g1", name: "Eagle Patrol" })

    render(
      <GroupMembershipEditor memberId="m1" memberGroups={[group]} allGroups={[group]} />,
    )

    await userEvent.click(screen.getByRole("button", { name: /remove from eagle patrol/i }))
    expect(mockRemove).toHaveBeenCalledWith(
      { groupId: "g1", memberId: "m1" },
      expect.anything(),
    )
  })

  it("offers no remove button for system groups", () => {
    const system = makeGroup({ id: "g1", name: "Everyone", is_system: true })

    render(
      <GroupMembershipEditor memberId="m1" memberGroups={[system]} allGroups={[system]} />,
    )
    expect(
      screen.queryByRole("button", { name: /remove from everyone/i }),
    ).not.toBeInTheDocument()
  })

  it("shows the create-groups hint when only system groups exist", () => {
    const system = makeGroup({ id: "g1", name: "Everyone", is_system: true })

    render(<GroupMembershipEditor memberId="m1" memberGroups={[]} allGroups={[system]} />)
    expect(screen.getByText(/no groups have been created yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/add to group/i)).not.toBeInTheDocument()
  })

  it("excludes current memberships and system groups from the add combobox", () => {
    const joined = makeGroup({ id: "g1", name: "Eagle Patrol" })
    const system = makeGroup({ id: "g2", name: "Everyone", is_system: true })
    const addable = makeGroup({ id: "g3", name: "Hawk Patrol" })

    render(
      <GroupMembershipEditor
        memberId="m1"
        memberGroups={[joined]}
        allGroups={[joined, system, addable]}
      />,
    )

    const popover = screen.getByTestId("popover-content")
    expect(within(popover).queryByText("Eagle Patrol")).not.toBeInTheDocument()
    expect(within(popover).queryByText("Everyone")).not.toBeInTheDocument()
    expect(within(popover).getByText("Hawk Patrol")).toBeInTheDocument()
  })

  it("adds the member when a group is selected", async () => {
    const group = makeGroup({ id: "g3", name: "Hawk Patrol" })

    render(<GroupMembershipEditor memberId="m1" memberGroups={[]} allGroups={[group]} />)

    const popover = screen.getByTestId("popover-content")
    await userEvent.click(within(popover).getByText("Hawk Patrol"))
    expect(mockAdd).toHaveBeenCalledWith({ groupId: "g3", memberId: "m1" })
  })
})
