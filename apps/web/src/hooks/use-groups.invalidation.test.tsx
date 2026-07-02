import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useUpdateGroup, useUpsertGroupRule, useDeleteGroupRule } from "./use-groups"

const TENANT = "tenant-1"

// Mock the HTTP + tenant layers so the hooks resolve without Clerk/network.
vi.mock("@/lib/api", () => ({
  useApi: () => ({ request: vi.fn().mockResolvedValue({}) }),
}))
vi.mock("@/lib/tenant-context", () => ({
  useActiveTenant: () => ({ activeTenantId: TENANT }),
}))

let queryClient: QueryClient
let invalidateSpy: ReturnType<typeof vi.spyOn>

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  queryClient = new QueryClient()
  invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")
})

function invalidatedKeys(): unknown[][] {
  return invalidateSpy.mock.calls.map((c: unknown[]) => (c[0] as { queryKey: unknown[] }).queryKey)
}

// The group resolution graph is transitive, so these membership-affecting mutations
// must invalidate the whole [tenant, "group-members"] key — not a single group.
describe("group cache invalidation", () => {
  it("useUpdateGroup invalidates all group-members (rule_logic / include_parents)", async () => {
    const { result } = renderHook(() => useUpdateGroup(), { wrapper })
    result.current.mutate({ id: "g1", data: { include_parents: true } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-members"])
    // The collapsed membership hooks read from the single /groups/roster cache.
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-roster"])
  })

  it("useUpsertGroupRule invalidates all group-members (dependent groups)", async () => {
    const { result } = renderHook(() => useUpsertGroupRule(), { wrapper })
    result.current.mutate({ groupId: "g1", dimension: "member_type", values: ["scout"] })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-members"])
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-roster"])
  })

  it("useDeleteGroupRule invalidates all group-members (dependent groups)", async () => {
    const { result } = renderHook(() => useDeleteGroupRule(), { wrapper })
    result.current.mutate({ groupId: "g1", dimension: "member_type" })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-members"])
    expect(invalidatedKeys()).toContainEqual([TENANT, "group-roster"])
  })
})
