import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

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

vi.mock("@/hooks/use-me", () => ({
  useMe: vi.fn(() => ({ data: undefined })),
}))

import { usePathname } from "next/navigation"
import { useMe } from "@/hooks/use-me"
import { AppSidebar } from "./app-sidebar"
import { SidebarProvider } from "./ui/sidebar"

function mockMe(value: unknown) {
  vi.mocked(useMe).mockReturnValue(value as ReturnType<typeof useMe>)
}

function renderSidebar() {
  return render(
    <SidebarProvider>
      <AppSidebar />
    </SidebarProvider>,
  )
}

describe("AppSidebar", () => {
  it("renders all five nav items", () => {
    renderSidebar()
    expect(screen.getByText("Members")).toBeInTheDocument()
    expect(screen.getByText("Groups")).toBeInTheDocument()
    expect(screen.getByText("Events")).toBeInTheDocument()
    expect(screen.getByText("Import")).toBeInTheDocument()
    expect(screen.getByText("Settings")).toBeInTheDocument()
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
    const membersButton = screen.getByText("Members").closest("[data-slot='sidebar-menu-button']")
    expect(eventsButton).toHaveAttribute("data-active", "")
    expect(membersButton).not.toHaveAttribute("data-active", "")
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

  it("shows the Platform link for platform admins", () => {
    mockMe({ data: { platform_role: "superadmin" } })
    renderSidebar()
    const link = screen.getByText("Platform").closest("a")
    expect(link).toHaveAttribute("href", "/platform")
  })
})
