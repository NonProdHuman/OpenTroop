import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/hooks/use-memberships", () => ({
  useMemberships: vi.fn(),
}))

vi.mock("@/lib/tenant-context", () => ({
  useActiveTenant: vi.fn(),
}))

// Sidebar primitives — render as semantic HTML so assertions are straightforward
vi.mock("@/components/ui/sidebar", () => ({
  SidebarMenu: ({ children }: { children: React.ReactNode }) => <ul>{children}</ul>,
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => <li>{children}</li>,
  SidebarMenuButton: ({
    children,
    ...props
  }: React.ComponentProps<"button">) => <button {...props}>{children}</button>,
}))

// Dropdown — render a simple select-like structure so we can test open/close/click
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({
    children,
    render: renderProp,
  }: {
    children?: React.ReactNode
    render?: React.ReactElement
  }) => {
    // base-ui uses a `render` prop; surface its children so tests can interact
    if (renderProp) {
      return (
        <div data-testid="dropdown-trigger">
          {children}
        </div>
      )
    }
    return <div data-testid="dropdown-trigger">{children}</div>
  },
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-content">{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onClick,
  }: {
    children: React.ReactNode
    onClick?: () => void
  }) => (
    <button role="menuitem" onClick={onClick}>
      {children}
    </button>
  ),
}))

import { useMemberships } from "@/hooks/use-memberships"
import { useActiveTenant } from "@/lib/tenant-context"
import { TenantSwitcher } from "./tenant-switcher"

const MEMBERSHIP_A = {
  tenant_id: "tenant-a",
  tenant_name: "Troop Alpha",
  tenant_slug: "troop-alpha",
  member_id: "member-a",
  is_admin: true,
}
const MEMBERSHIP_B = {
  tenant_id: "tenant-b",
  tenant_name: "Troop Beta",
  tenant_slug: "troop-beta",
  member_id: "member-b",
  is_admin: false,
}

function mockMemberships(
  memberships: typeof MEMBERSHIP_A[],
  isLoading = false,
) {
  vi.mocked(useMemberships).mockReturnValue({
    data: memberships,
    isLoading,
  } as ReturnType<typeof useMemberships>)
}

function mockTenant(activeTenantId: string, setActiveTenantId = vi.fn()) {
  vi.mocked(useActiveTenant).mockReturnValue({ activeTenantId, setActiveTenantId })
}

describe("TenantSwitcher", () => {
  beforeEach(() => {
    mockMemberships([])
    mockTenant("")
  })

  // ── Static label (single/no membership) ──────────────────────────────────

  it("shows 'No troop selected' when there are no memberships", () => {
    mockMemberships([])
    mockTenant("")
    render(<TenantSwitcher />)
    expect(screen.getByText("No troop selected")).toBeInTheDocument()
  })

  it("shows the troop name statically when the user belongs to exactly one troop", () => {
    mockMemberships([MEMBERSHIP_A])
    mockTenant("tenant-a")
    render(<TenantSwitcher />)
    expect(screen.getByText("Troop Alpha")).toBeInTheDocument()
    // No dropdown trigger when there is only one option
    expect(screen.queryByTestId("dropdown-trigger")).not.toBeInTheDocument()
  })

  it("does not render a dropdown for a single membership", () => {
    mockMemberships([MEMBERSHIP_A])
    mockTenant("tenant-a")
    render(<TenantSwitcher />)
    expect(screen.queryByRole("menuitem")).not.toBeInTheDocument()
  })

  // ── Dropdown (multiple memberships) ──────────────────────────────────────

  it("renders a dropdown trigger when the user belongs to multiple troops", () => {
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("tenant-a")
    render(<TenantSwitcher />)
    expect(screen.getByTestId("dropdown-trigger")).toBeInTheDocument()
  })

  it("lists all memberships as menu items", () => {
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("tenant-a")
    render(<TenantSwitcher />)
    expect(screen.getByRole("menuitem", { name: /Troop Alpha/ })).toBeInTheDocument()
    expect(screen.getByRole("menuitem", { name: /Troop Beta/ })).toBeInTheDocument()
  })

  it("calls setActiveTenantId with the chosen tenant when a menu item is clicked", async () => {
    const setActiveTenantId = vi.fn()
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("tenant-a", setActiveTenantId)
    render(<TenantSwitcher />)

    await userEvent.click(screen.getByRole("menuitem", { name: /Troop Beta/ }))

    expect(setActiveTenantId).toHaveBeenCalledWith("tenant-b")
  })

  it("shows a checkmark next to the active membership", () => {
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("tenant-a")
    render(<TenantSwitcher />)

    // lucide-react Check renders an <svg>; confirm it appears in the active item only
    const activeItem = screen.getByRole("menuitem", { name: /Troop Alpha/ })
    const inactiveItem = screen.getByRole("menuitem", { name: /Troop Beta/ })

    expect(activeItem.querySelector("svg")).toBeInTheDocument()
    expect(inactiveItem.querySelector("svg")).toBeInTheDocument() // Building2 icon

    // Active item has two SVGs (Building2 + Check), inactive item has one (Building2 only)
    expect(activeItem.querySelectorAll("svg").length).toBe(2)
    expect(inactiveItem.querySelectorAll("svg").length).toBe(1)
  })

  it("displays the active tenant name in the trigger for multiple memberships", () => {
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("tenant-b")
    render(<TenantSwitcher />)
    // The trigger contains a <span class="truncate font-semibold"> with the active name.
    // getAllByText because the same name also appears in the dropdown item.
    const matches = screen.getAllByText("Troop Beta")
    const triggerLabel = matches.find((el) => el.classList.contains("truncate"))
    expect(triggerLabel).toBeInTheDocument()
  })

  it("shows 'Select troop' in the trigger when activeTenantId matches no membership", () => {
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B])
    mockTenant("unknown-id")
    render(<TenantSwitcher />)
    expect(screen.getByText("Select troop")).toBeInTheDocument()
  })

  // ── Auto-select ───────────────────────────────────────────────────────────

  it("auto-selects the first membership when activeTenantId is empty", async () => {
    const setActiveTenantId = vi.fn()
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B], false)
    mockTenant("", setActiveTenantId)
    render(<TenantSwitcher />)

    await waitFor(() => {
      expect(setActiveTenantId).toHaveBeenCalledWith("tenant-a")
    })
  })

  it("does not auto-select when a tenant is already active", async () => {
    const setActiveTenantId = vi.fn()
    mockMemberships([MEMBERSHIP_A, MEMBERSHIP_B], false)
    mockTenant("tenant-b", setActiveTenantId)
    render(<TenantSwitcher />)

    // Give effects time to run
    await waitFor(() => {})

    expect(setActiveTenantId).not.toHaveBeenCalled()
  })

  it("does not auto-select while memberships are still loading", async () => {
    const setActiveTenantId = vi.fn()
    mockMemberships([], true /* isLoading */)
    mockTenant("", setActiveTenantId)
    render(<TenantSwitcher />)

    await waitFor(() => {})

    expect(setActiveTenantId).not.toHaveBeenCalled()
  })
})
