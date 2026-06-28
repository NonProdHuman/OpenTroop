/* eslint-disable @typescript-eslint/no-explicit-any */
import React from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import FunctionalRolesPage from "./page"
import * as functionalRolesHook from "@/hooks/use-functional-roles"
import * as sessionHook from "@/hooks/use-session"
import type { FunctionalRole, FunctionalRolePermission } from "@/types/api"

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

vi.mock("@/hooks/use-functional-roles", () => ({
  useFunctionalRoles: vi.fn(),
  useDeleteFunctionalRole: vi.fn(),
  useFunctionalRolePermissions: vi.fn(),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const makeRole = (overrides: Partial<FunctionalRole>): FunctionalRole => ({
  id: "r1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  name: "Event Admins",
  slug: "event-admins",
  is_system: false,
  is_admin: false,
  ...overrides,
})

const makePermission = (perm: string): FunctionalRolePermission => ({
  id: "fp1",
  tenant_id: "t1",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  is_deleted: false,
  functional_role_id: "r1",
  permission: perm as any,
})

describe("FunctionalRolesPage", () => {
  const mockDelete = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [],
      isLoading: false,
    } as any)

    vi.mocked(functionalRolesHook.useDeleteFunctionalRole).mockReturnValue({
      mutate: mockDelete,
      isPending: false,
    } as any)

    vi.mocked(functionalRolesHook.useFunctionalRolePermissions).mockReturnValue({
      data: [],
    } as any)

    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => true,
      isMember: true,
      isLoading: false,
    } as any)
  })

  it("renders the page header", () => {
    render(<FunctionalRolesPage />)
    expect(screen.getByRole("heading", { name: "Functional Roles" })).toBeInTheDocument()
  })

  it("shows empty state when no roles exist", () => {
    render(<FunctionalRolesPage />)
    expect(screen.getByText("No functional roles yet.")).toBeInTheDocument()
  })

  it("shows 'New role' button when user has role:manage", () => {
    // Provide data so empty state (with its own "New role" button) is not shown
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({})],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)
    render(<FunctionalRolesPage />)
    expect(screen.getByRole("button", { name: /new role/i })).toBeInTheDocument()
  })

  it("hides 'New role' button when user lacks role:manage", () => {
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: () => false,
      isMember: true,
      isLoading: false,
    } as any)
    render(<FunctionalRolesPage />)
    expect(screen.queryByRole("button", { name: /new role/i })).not.toBeInTheDocument()
  })

  it("renders roles in the table", () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [
        makeRole({ id: "r1", name: "Event Admins" }),
        makeRole({ id: "r2", name: "Member Admins" }),
      ],
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    expect(screen.getByText("Event Admins")).toBeInTheDocument()
    expect(screen.getByText("Member Admins")).toBeInTheDocument()
  })

  it("renders a 'System roles' separator for system roles", () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [
        makeRole({ id: "r1", name: "Event Admins", is_system: false }),
        makeRole({ id: "r2", name: "Administrators", is_system: true, is_admin: true }),
      ],
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    expect(screen.getByText("System roles")).toBeInTheDocument()
    expect(screen.getByText("Administrators")).toBeInTheDocument()
  })

  it("shows loading state", () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)

    render(<FunctionalRolesPage />)
    expect(screen.getByText("Loading…")).toBeInTheDocument()
  })

  it("opens the detail sheet when a row is clicked", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Event Admins" })],
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Event Admins"))
    expect(screen.getAllByText("Event Admins").length).toBeGreaterThan(1)
  })

  it("shows 'No permissions granted' in sheet when role has no permissions", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Event Admins", is_admin: false })],
      isLoading: false,
    } as any)
    vi.mocked(functionalRolesHook.useFunctionalRolePermissions).mockReturnValue({
      data: [],
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Event Admins"))
    expect(screen.getByText("No permissions granted.")).toBeInTheDocument()
  })

  it("shows grouped permissions in the detail sheet", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Event Admins", is_admin: false })],
      isLoading: false,
    } as any)
    vi.mocked(functionalRolesHook.useFunctionalRolePermissions).mockReturnValue({
      data: [
        makePermission("event:read"),
        makePermission("event:create"),
      ],
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Event Admins"))
    expect(screen.getByText("Event — View")).toBeInTheDocument()
    expect(screen.getByText("Event — Create")).toBeInTheDocument()
  })

  it("shows admin shortcut banner for is_admin roles", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Administrators", is_admin: true, is_system: true })],
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Administrators"))
    // "all permissions" lives inside a <strong> child of the banner <p>
    expect(screen.getByText(/all permissions/i)).toBeInTheDocument()
  })

  it("shows Edit button in sheet for role:manage holders", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Event Admins" })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Event Admins"))
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument()
  })

  it("hides Delete button for system roles", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Administrators", is_system: true })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Administrators"))
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument()
  })

  it("requires confirm before deleting a non-system role", async () => {
    vi.mocked(functionalRolesHook.useFunctionalRoles).mockReturnValue({
      data: [makeRole({ id: "r1", name: "Event Admins", is_system: false })],
      isLoading: false,
    } as any)
    vi.mocked(sessionHook.usePermissions).mockReturnValue({
      has: (p: string) => p === "role:manage",
      isMember: true,
      isLoading: false,
    } as any)

    render(<FunctionalRolesPage />)
    await userEvent.click(screen.getByText("Event Admins"))

    const deleteBtn = screen.getByRole("button", { name: /^delete$/i })
    await userEvent.click(deleteBtn)
    expect(screen.getByRole("button", { name: /confirm delete/i })).toBeInTheDocument()
    expect(mockDelete).not.toHaveBeenCalled()
  })
})
