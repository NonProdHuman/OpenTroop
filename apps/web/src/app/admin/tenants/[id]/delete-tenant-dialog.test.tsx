import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Tenant } from "@/types/api"
import * as platformHook from "@/hooks/use-platform"
import { DeleteTenantDialog, deleteGatesSatisfied } from "./delete-tenant-dialog"

const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/hooks/use-platform", () => ({
  useDeleteTenant: vi.fn(),
}))

function tenant(over: Partial<Tenant> = {}): Tenant {
  return {
    id: "t1",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    is_deleted: false,
    name: "Troop 666",
    slug: "troop666",
    suspended_at: "2026-07-01T00:00:00Z",
    last_export_at: "2026-07-02T00:00:00Z",
    ...over,
  }
}

const mutateAsync = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(platformHook.useDeleteTenant).mockReturnValue({
    mutateAsync,
    isPending: false,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any)
})

describe("deleteGatesSatisfied", () => {
  it("requires suspension", () => {
    expect(deleteGatesSatisfied(tenant({ suspended_at: null }))).toBe(false)
  })

  it("requires an export taken after suspension", () => {
    expect(deleteGatesSatisfied(tenant({ last_export_at: null }))).toBe(false)
    expect(
      deleteGatesSatisfied(tenant({ last_export_at: "2026-06-30T00:00:00Z" })),
    ).toBe(false)
    expect(deleteGatesSatisfied(tenant())).toBe(true)
  })
})

describe("DeleteTenantDialog", () => {
  it("disables the trigger until the gates are satisfied", () => {
    render(<DeleteTenantDialog tenant={tenant({ suspended_at: null })} />)
    expect(screen.getByRole("button", { name: /delete tenant…/i })).toBeDisabled()
  })

  it("requires typing the exact slug before deleting", async () => {
    const user = userEvent.setup()
    render(<DeleteTenantDialog tenant={tenant()} />)
    await user.click(screen.getByRole("button", { name: /delete tenant…/i }))

    const confirmButton = screen.getByRole("button", { name: /^delete tenant$/i })
    expect(confirmButton).toBeDisabled()

    await user.type(screen.getByLabelText(/type/i), "troop-666") // close, but not the slug
    expect(confirmButton).toBeDisabled()

    await user.clear(screen.getByLabelText(/type/i))
    await user.type(screen.getByLabelText(/type/i), "troop666")
    expect(confirmButton).toBeEnabled()

    await user.click(confirmButton)
    expect(mutateAsync).toHaveBeenCalledWith("troop666")
    expect(mockPush).toHaveBeenCalledWith("/tenants")
  })
})
