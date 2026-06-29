import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { TenantStatusBadge } from "./tenant-status-badge"

describe("TenantStatusBadge", () => {
  it("shows Active when not suspended", () => {
    render(<TenantStatusBadge tenant={{ suspended_at: null }} />)
    expect(screen.getByText("Active")).toBeInTheDocument()
    expect(screen.queryByText("Suspended")).not.toBeInTheDocument()
  })

  it("shows Suspended when a suspension timestamp is set", () => {
    render(<TenantStatusBadge tenant={{ suspended_at: "2026-01-01T00:00:00Z" }} />)
    expect(screen.getByText("Suspended")).toBeInTheDocument()
    expect(screen.queryByText("Active")).not.toBeInTheDocument()
  })
})
