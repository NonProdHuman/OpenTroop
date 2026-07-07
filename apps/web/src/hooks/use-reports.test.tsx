import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useReport, useReportCatalog } from "./use-reports"

const TENANT = "tenant-1"

const requestSpy = vi.fn().mockResolvedValue({ rows: [], columns: [] })
vi.mock("@/lib/api", () => ({
  useApi: () => ({ request: requestSpy, requestBlob: vi.fn() }),
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

describe("report hooks", () => {
  it("useReportCatalog requests /reports with no trailing slash", async () => {
    renderHook(() => useReportCatalog(), { wrapper })
    await waitFor(() => expect(requestSpy).toHaveBeenCalled())
    expect(lastPath()).toBe("/reports")
  })

  it("useReport appends non-empty params and format=json", async () => {
    renderHook(() => useReport("roster", { member_type: "scout", group_id: "" }), { wrapper })
    await waitFor(() => expect(requestSpy).toHaveBeenCalled())
    const path = lastPath()
    expect(path.startsWith("/reports/roster?")).toBe(true)
    expect(path).toContain("member_type=scout")
    expect(path).toContain("format=json")
    // Empty values are dropped, not sent as blanks.
    expect(path).not.toContain("group_id=")
  })

  it("useReport is disabled until a key is supplied", () => {
    renderHook(() => useReport(null, {}), { wrapper })
    expect(requestSpy).not.toHaveBeenCalled()
  })
})
