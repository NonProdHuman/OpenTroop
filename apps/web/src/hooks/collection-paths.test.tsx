import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useEvents, useEventTypes, useLocations, useCreateEvent } from "./use-events"
import { useFunctionalRoles, useCreateFunctionalRole } from "./use-functional-roles"
import { useGroups, useCreateGroup } from "./use-groups"
import { useMembers, useCreateMember } from "./use-members"
import { usePositions, useCreatePosition } from "./use-positions"
import { useCreateRelationship } from "./use-relationships"

const TENANT = "tenant-1"

// Capture every path passed to request() across all hooks.
const requestSpy = vi.fn().mockResolvedValue([])
vi.mock("@/lib/api", () => ({
  useApi: () => ({ request: requestSpy }),
}))
vi.mock("@/lib/tenant-context", () => ({
  useActiveTenant: () => ({ activeTenantId: TENANT }),
}))

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  queryClient = new QueryClient()
  requestSpy.mockClear()
})

function lastPath(): string {
  return requestSpy.mock.calls.at(-1)![0] as string
}

// Collection roots must be requested WITHOUT a trailing slash. Backend collection
// routes live at "" (canonical /foo). Requesting /foo/ makes the backend 307-redirect
// to /foo, and because /api/* is proxied cross-origin, the browser drops the Clerk
// Authorization header on that redirect -> 401 / empty lists. Regression guard for
// commit 6e6dee5 and issue #97.
describe("collection paths have no trailing slash", () => {
  const listHooks: [string, () => unknown, string][] = [
    ["useMembers", useMembers, "/members"],
    ["useGroups", useGroups, "/groups"],
    ["usePositions", usePositions, "/positions"],
    ["useFunctionalRoles", useFunctionalRoles, "/functional-roles"],
    ["useEvents", useEvents, "/events"],
    ["useEventTypes", useEventTypes, "/event-types"],
    ["useLocations", useLocations, "/locations"],
  ]

  it.each(listHooks)("%s requests %s", async (_name, hook, path) => {
    renderHook(() => hook(), { wrapper })
    await waitFor(() => expect(requestSpy).toHaveBeenCalled())
    expect(lastPath()).toBe(path)
    expect(lastPath().endsWith("/")).toBe(false)
  })

  const createHooks: [string, () => { mutate: (v: never) => void }, string][] = [
    ["useCreateMember", useCreateMember, "/members"],
    ["useCreateGroup", useCreateGroup, "/groups"],
    ["useCreatePosition", useCreatePosition, "/positions"],
    ["useCreateFunctionalRole", useCreateFunctionalRole, "/functional-roles"],
    ["useCreateEvent", useCreateEvent, "/events"],
    ["useCreateRelationship", useCreateRelationship, "/relationships"],
  ]

  it.each(createHooks)("%s posts to %s", async (_name, hook, path) => {
    const { result } = renderHook(() => hook(), { wrapper })
    result.current.mutate({} as never)
    await waitFor(() => expect(requestSpy).toHaveBeenCalled())
    expect(lastPath()).toBe(path)
  })
})
