/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import PositionsPage from "./page"
import * as positionsHook from "@/hooks/use-positions"
import * as functionalRolesHook from "@/hooks/use-functional-roles"
import * as sessionHook from "@/hooks/use-session"
import type { Position } from "@/types/api"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/components/page-header", () => ({
  PageHeader: ({ title, children }: { title: string; children?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}))

vi.mock("@/hooks/use-positions", () => ({
  usePositions: vi.fn(),
  useDeletePosition: vi.fn(),
  usePositionFunctionalRoles: vi.fn(),
}))

vi.mock("@/hooks/use-functional-roles", () => ({
  useFunctionalRoles: vi.fn(),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
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

describe("PositionsPage", () => {
  const mockDelete = vi.fn()
  const mockPush = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [],
      isLoading: false,
    } as any)

    vi.mocked(positionsHook.useDeletePosition).mockReturnValue({
      mutate: mockDelete,
      isPending: false,
    } as any)

    vi.mocked(positionsHook.usePositionFunctionalRoles).mockReturnValue({
      data: [],
    } as any)

    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [],
    } as any)

    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => true,
      isMember: true,
      isLoading: false,
    } as any)

    vi.mocked(vi.fn()).mockImplementation(() => ({ push: mockPush }))
  })

  it("renders the page header", () => {
    render(<PositionsPage />)
    expect(screen.getByRole("heading", { name: "Positions" })).toBeInTheDocument()
  })

  it("shows empty state when no positions exist", () => {
    render(<PositionsPage />)
    expect(screen.getByText("No positions yet.")).toBeInTheDocument()
  })

  it("shows 'New position' button when user has role:manage", () => {
    // Provide data so empty state (with its own "New position" button) is not shown
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({})],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)
    render(<PositionsPage />)
    expect(screen.getByRole("button", { name: /new position/i })).toBeInTheDocument()
  })

  it("hides 'New position' button when user lacks role:manage", () => {
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => false,
      isMember: true,
      isLoading: false,
    } as any)
    render(<PositionsPage />)
    expect(screen.queryByRole("button", { name: /new position/i })).not.toBeInTheDocument()
  })

  it("renders non-system positions in the table", () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [
        makePosition({ id: "p1", name: "Patrol Leader", applies_to: "scout" }),
        makePosition({ id: "p2", name: "Committee Chair", applies_to: "adult" }),
      ],
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    expect(screen.getByText("Patrol Leader")).toBeInTheDocument()
    expect(screen.getByText("Committee Chair")).toBeInTheDocument()
  })

  it("renders scope badges correctly", () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [
        makePosition({ id: "p1", name: "Patrol Leader", applies_to: "scout" }),
        makePosition({ id: "p2", name: "Committee Chair", applies_to: "adult" }),
        makePosition({ id: "p3", name: "Treasurer", applies_to: "any" }),
      ],
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    expect(screen.getByText("Scout")).toBeInTheDocument()
    expect(screen.getByText("Adult")).toBeInTheDocument()
    expect(screen.getByText("Any")).toBeInTheDocument()
  })

  it("renders system positions alongside non-system positions", () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [
        makePosition({ id: "p1", name: "Patrol Leader", is_system: false }),
        makePosition({ id: "p2", name: "Scoutmaster", is_system: true }),
      ],
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    expect(screen.getByText("Patrol Leader")).toBeInTheDocument()
    expect(screen.getByText("Scoutmaster")).toBeInTheDocument()
    expect(screen.queryByText("System positions")).not.toBeInTheDocument()
  })

  it("shows loading state", () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)

    render(<PositionsPage />)
    expect(screen.getByText("Loading…")).toBeInTheDocument()
  })

  it("opens the detail sheet when a row is clicked", async () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({ id: "p1", name: "Patrol Leader" })],
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    await userEvent.click(screen.getByText("Patrol Leader"))
    // Sheet renders with the position title
    expect(screen.getAllByText("Patrol Leader").length).toBeGreaterThan(1)
  })

  it("shows Edit button in detail sheet for role:manage holders", async () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({ id: "p1", name: "Patrol Leader" })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    await userEvent.click(screen.getByText("Patrol Leader"))
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument()
  })

  it("hides Edit button in detail sheet when user lacks role:manage", async () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({ id: "p1", name: "Patrol Leader" })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => false,
      isMember: true,
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    await userEvent.click(screen.getByText("Patrol Leader"))
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument()
  })

  it("requires confirm before deleting a non-system position", async () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({ id: "p1", name: "Patrol Leader", is_system: false })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    await userEvent.click(screen.getByText("Patrol Leader"))

    const deleteBtn = screen.getByRole("button", { name: /^delete$/i })
    await userEvent.click(deleteBtn)
    expect(screen.getByRole("button", { name: /confirm delete/i })).toBeInTheDocument()
    expect(mockDelete).not.toHaveBeenCalled()
  })

  it("hides Delete button for system positions", async () => {
    vi.mocked(positionsHook.usePositions).mockReturnValue({
      data: [makePosition({ id: "p1", name: "Scoutmaster", is_system: true })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<PositionsPage />)
    await userEvent.click(screen.getByText("Scoutmaster"))
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument()
  })
})
