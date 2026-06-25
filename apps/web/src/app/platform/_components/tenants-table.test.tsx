import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

import type { Tenant } from "@/types/api"
import { TenantsTable } from "./tenants-table"

function tenant(over: Partial<Tenant> = {}): Tenant {
  return {
    id: "t1",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    is_deleted: false,
    name: "Troop 42",
    slug: "troop42",
    suspended_at: null,
    ...over,
  }
}

describe("TenantsTable", () => {
  it("renders a row per tenant linking to its detail page", () => {
    render(<TenantsTable tenants={[tenant()]} />)
    const link = screen.getByText("Troop 42").closest("a")
    expect(link).toHaveAttribute("href", "/platform/tenants/t1")
    expect(screen.getByText("troop42")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("reflects suspended status", () => {
    render(<TenantsTable tenants={[tenant({ suspended_at: "2026-06-02T00:00:00Z" })]} />)
    expect(screen.getByText("Suspended")).toBeInTheDocument()
  })

  it("shows an empty state when there are no tenants", () => {
    render(<TenantsTable tenants={[]} />)
    expect(screen.getByText(/no tenants yet/i)).toBeInTheDocument()
  })

  it("renders skeleton placeholders while loading", () => {
    const { container } = render(<TenantsTable tenants={[]} isLoading />)
    expect(screen.queryByText(/no tenants yet/i)).not.toBeInTheDocument()
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })
})
