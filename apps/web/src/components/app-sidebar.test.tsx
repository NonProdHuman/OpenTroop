import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

// Must be hoisted above the component import
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/members"),
}))

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@clerk/nextjs", () => ({
  UserButton: () => <div data-testid="user-button" />,
}))

vi.mock("@/hooks/use-memberships", () => ({
  useMemberships: vi.fn(() => ({ data: [], isLoading: false })),
}))

vi.mock("@/lib/tenant-context", () => ({
  TenantProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useActiveTenant: vi.fn(() => ({ activeTenantId: "test-tenant", setActiveTenantId: vi.fn() })),
}))

vi.mock("@/hooks/use-me", () => ({
  useMe: vi.fn(() => ({ data: undefined })),
}))

vi.mock("@/hooks/use-session", () => ({
  usePermissions: vi.fn(() => ({ has: () => true, isMember: true, isLoading: false })),
}))

import { usePathname } from "next/navigation"
import { useMe } from "@/hooks/use-me"
import { usePermissions } from "@/hooks/use-session"
import { AppSidebar } from "./app-sidebar"
import { SidebarProvider } from "./ui/sidebar"

function mockMe(value: unknown) {
  vi.mocked(useMe).mockReturnValue(value as ReturnType<typeof useMe>)
}

function mockPermissions(has: (p: string) => boolean) {
  vi.mocked(usePermissions).mockReturnValue({
    has: has as ReturnType<typeof usePermissions>["has"],
    isMember: true,
    isLoading: false,
  })
}

function renderSidebar() {
  return render(
    <SidebarProvider>
      <AppSidebar />
    </SidebarProvider>,
  )
}

describe("AppSidebar", () => {
  beforeEach(() => {
    // Reset to a non-Admin route so the Admin group starts collapsed.
    vi.mocked(usePathname).mockReturnValue("/members")
    // Default: all permissions granted
    vi.mocked(usePermissions).mockReturnValue({
      has: () => true,
      isMember: true,
      isLoading: false,
    })
  })

  it("renders the top-level nav items", () => {
    renderSidebar()
    expect(screen.getByText("Members")).toBeInTheDocument()
    expect(screen.getByText("Groups")).toBeInTheDocument()
    expect(screen.getByText("Events")).toBeInTheDocument()
    expect(screen.getByText("Admin")).toBeInTheDocument()
  })

  it("renders the grayed-out future nav items", () => {
    renderSidebar()
    expect(screen.getByText("Messaging")).toBeInTheDocument()
    expect(screen.getByText("Advancement")).toBeInTheDocument()
    expect(screen.getByText("Reports")).toBeInTheDocument()
  })

  it("keeps Admin sub-items collapsed until the group is opened", () => {
    renderSidebar() // default pathname is /members → Admin collapsed
    expect(screen.queryByText("Settings")).not.toBeInTheDocument()
    expect(screen.queryByText("Import")).not.toBeInTheDocument()
  })

  it("expands the Admin group to reveal its sub-items on click", async () => {
    renderSidebar()
    await userEvent.click(screen.getByText("Admin"))
    expect(screen.getByText("Settings").closest("a")).toHaveAttribute("href", "/settings")
    expect(screen.getByText("Import").closest("a")).toHaveAttribute("href", "/import")
  })

  it("auto-expands the group containing the active route", () => {
    vi.mocked(usePathname).mockReturnValue("/import")
    renderSidebar()
    // Admin opens automatically because /import is one of its children.
    const importLink = screen.getByText("Import").closest("[data-slot='sidebar-menu-sub-button']")
    expect(importLink).toHaveAttribute("data-active", "")
  })

  it("nav items link to the correct paths", () => {
    renderSidebar()
    expect(screen.getByText("Members").closest("a")).toHaveAttribute("href", "/members")
    expect(screen.getByText("Events").closest("a")).toHaveAttribute("href", "/events")
  })

  it("marks the current route as active", () => {
    vi.mocked(usePathname).mockReturnValue("/events")
    renderSidebar()
    // shadcn sidebar sets data-active="" (empty string = present) on the active button
    const eventsButton = screen.getByText("Events").closest("[data-slot='sidebar-menu-button']")
    expect(eventsButton).toHaveAttribute("data-active", "")
    // "Members" is in the collapsed "Membership" group, so it should not render
    expect(screen.queryByText("Members")).not.toBeInTheDocument()
  })

  it("renders the user button in the footer", () => {
    renderSidebar()
    expect(screen.getByTestId("user-button")).toBeInTheDocument()
  })

  it("renders the OpenTroop brand mark", () => {
    renderSidebar()
    expect(screen.getByText("OpenTroop")).toBeInTheDocument()
    expect(screen.getByText("OT")).toBeInTheDocument()
  })

  it("hides the Platform link for non-platform-admins", () => {
    mockMe({ data: { platform_role: null } })
    renderSidebar()
    expect(screen.queryByText("Platform")).not.toBeInTheDocument()
  })

  it("shows the Platform link for platform admins", async () => {
    mockMe({ data: { platform_role: "superadmin" } })
    renderSidebar()
    expect(screen.getByText("Platform")).toBeInTheDocument()
    await userEvent.click(screen.getByText("Platform"))
    expect(screen.getByText("Tenants").closest("a")).toHaveAttribute("href", "/platform/tenants")
    expect(screen.getByText("Admins").closest("a")).toHaveAttribute("href", "/platform/admins")
  })

  it("hides nav items whose required permission is absent", async () => {
    mockPermissions((p) => p !== "member:read")
    renderSidebar()
    // Events requires event:read which is granted
    expect(screen.getByText("Events")).toBeInTheDocument()
    // Expand Membership group
    await userEvent.click(screen.getByText("Membership"))
    expect(screen.queryByText("Members")).not.toBeInTheDocument()
    expect(screen.queryByText("Groups")).not.toBeInTheDocument()
    expect(screen.getByText("Positions")).toBeInTheDocument()
    expect(screen.getByText("Functional Roles")).toBeInTheDocument()
  })

  it("shows nav items when the required permission is present", () => {
    mockPermissions(() => true)
    renderSidebar()
    expect(screen.getByText("Members")).toBeInTheDocument()
    expect(screen.getByText("Events")).toBeInTheDocument()
  })
})
