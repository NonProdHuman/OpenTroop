import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { PlatformAdmin } from "@/types/api"
import { AdminsTable } from "./admins-table"

function admin(over: Partial<PlatformAdmin> = {}): PlatformAdmin {
  return {
    user_id: "u1",
    email: "boss@example.com",
    display_name: "Boss Person",
    platform_role: "superadmin",
    ...over,
  }
}

describe("AdminsTable", () => {
  it("renders a row per admin with role", () => {
    render(<AdminsTable admins={[admin()]} />)
    expect(screen.getByText("Boss Person")).toBeInTheDocument()
    expect(screen.getByText("boss@example.com")).toBeInTheDocument()
    expect(screen.getByText("superadmin")).toBeInTheDocument()
  })

  it("hides the Revoke action when the viewer cannot manage", () => {
    render(<AdminsTable admins={[admin()]} canManage={false} />)
    expect(screen.queryByText("Revoke")).not.toBeInTheDocument()
  })

  it("calls onRevoke when managing and Revoke is clicked", () => {
    const onRevoke = vi.fn()
    render(<AdminsTable admins={[admin()]} canManage onRevoke={onRevoke} />)
    screen.getByText("Revoke").click()
    expect(onRevoke).toHaveBeenCalledWith(expect.objectContaining({ user_id: "u1" }))
  })

  it("shows an empty state when there are no admins", () => {
    render(<AdminsTable admins={[]} />)
    expect(screen.getByText(/no platform administrators/i)).toBeInTheDocument()
  })
})
