import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  useCreateTenant,
  useGrantPlatformAdmin,
  useInviteTenantAdmin,
  usePlatformAdmins,
  useRevokePlatformAdmin,
  useRevokeTenantAdmin,
  useSetTenantSuspended,
  useTenant,
  useTenantAdmins,
  useTenants,
} from "./use-platform"

// Mock the HTTP layer so the hooks resolve without Clerk/network.
const requestMock = vi.hoisted(() => vi.fn())
vi.mock("@/lib/api", () => ({
  useApi: () => ({ request: requestMock }),
}))

let queryClient: QueryClient
let invalidateSpy: ReturnType<typeof vi.spyOn>

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  requestMock.mockReset().mockResolvedValue({})
  queryClient = new QueryClient()
  invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
})

function invalidatedKeys(): unknown[][] {
  return invalidateSpy.mock.calls.map((c: unknown[]) => (c[0] as { queryKey: unknown[] }).queryKey)
}

describe("platform control-plane hooks", () => {
  it("query hooks fetch from their /platform endpoints", async () => {
    const tenants = renderHook(() => useTenants(), { wrapper })
    const tenant = renderHook(() => useTenant("t1"), { wrapper })
    const admins = renderHook(() => useTenantAdmins("t1"), { wrapper })
    const platformAdmins = renderHook(() => usePlatformAdmins(), { wrapper })

    await waitFor(() => expect(tenants.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(tenant.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(admins.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(platformAdmins.result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith("/platform/tenants")
    expect(requestMock).toHaveBeenCalledWith("/platform/tenants/t1")
    expect(requestMock).toHaveBeenCalledWith("/platform/tenants/t1/admins")
    expect(requestMock).toHaveBeenCalledWith("/platform/admins")
  })

  it("useTenant and useTenantAdmins stay disabled without an id", () => {
    const tenant = renderHook(() => useTenant(""), { wrapper })
    const admins = renderHook(() => useTenantAdmins(""), { wrapper })

    expect(tenant.result.current.fetchStatus).toBe("idle")
    expect(admins.result.current.fetchStatus).toBe("idle")
    expect(requestMock).not.toHaveBeenCalled()
  })

  it("useCreateTenant posts to /platform/tenants and invalidates the tenant list", async () => {
    const { result } = renderHook(() => useCreateTenant(), { wrapper })
    result.current.mutate({
      name: "Troop 123",
      slug: "troop123",
      founder_first_name: "A",
      founder_last_name: "B",
      founder_email: "a@example.com",
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith(
      "/platform/tenants",
      expect.objectContaining({ method: "POST" }),
    )
    expect(invalidatedKeys()).toContainEqual(["platform", "tenants"])
  })

  it("useSetTenantSuspended(true) posts to /suspend and refreshes tenant + list", async () => {
    const { result } = renderHook(() => useSetTenantSuspended("t1"), { wrapper })
    result.current.mutate(true)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith("/platform/tenants/t1/suspend", { method: "POST" })
    expect(invalidatedKeys()).toContainEqual(["platform", "tenant", "t1"])
    expect(invalidatedKeys()).toContainEqual(["platform", "tenants"])
  })

  it("useSetTenantSuspended(false) posts to /unsuspend", async () => {
    const { result } = renderHook(() => useSetTenantSuspended("t1"), { wrapper })
    result.current.mutate(false)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith("/platform/tenants/t1/unsuspend", { method: "POST" })
  })

  it("useInviteTenantAdmin posts to the tenant's admins and invalidates them", async () => {
    const { result } = renderHook(() => useInviteTenantAdmin("t1"), { wrapper })
    result.current.mutate({ first_name: "A", last_name: "B", email: "a@example.com" })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith(
      "/platform/tenants/t1/admins",
      expect.objectContaining({ method: "POST" }),
    )
    expect(invalidatedKeys()).toContainEqual(["platform", "tenant", "t1", "admins"])
  })

  it("useRevokeTenantAdmin deletes the member's admin row and invalidates admins", async () => {
    const { result } = renderHook(() => useRevokeTenantAdmin("t1"), { wrapper })
    result.current.mutate("m1")
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith("/platform/tenants/t1/admins/m1", {
      method: "DELETE",
    })
    expect(invalidatedKeys()).toContainEqual(["platform", "tenant", "t1", "admins"])
  })

  it("useGrantPlatformAdmin posts to /platform/admins and invalidates the admin list", async () => {
    const { result } = renderHook(() => useGrantPlatformAdmin(), { wrapper })
    result.current.mutate({ email: "a@example.com", role: "support" })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith(
      "/platform/admins",
      expect.objectContaining({ method: "POST" }),
    )
    expect(invalidatedKeys()).toContainEqual(["platform", "admins"])
  })

  it("useRevokePlatformAdmin deletes the grant and invalidates the admin list", async () => {
    const { result } = renderHook(() => useRevokePlatformAdmin(), { wrapper })
    result.current.mutate("u1")
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(requestMock).toHaveBeenCalledWith("/platform/admins/u1", { method: "DELETE" })
    expect(invalidatedKeys()).toContainEqual(["platform", "admins"])
  })
})
