import { renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, apiErrorMessage, useApi } from "./api"

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
}))

vi.mock("@/lib/tenant-context", () => ({
  useActiveTenant: () => ({ activeTenantId: "tenant-1" }),
}))

describe("useApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("throws an ApiError carrying the HTTP status on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"A group with this name already exists"}', { status: 409 }),
      ),
    )

    const { result } = renderHook(() => useApi())
    const err = await result.current.request("/groups").catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(409)
    expect((err as ApiError).message).toContain("already exists")
  })
})

describe("apiErrorMessage", () => {
  it("surfaces the page-specific message for a matched status (409 conflict)", () => {
    const msg = apiErrorMessage(new ApiError(409, "duplicate"), {
      409: "A group with this name already exists.",
    })
    expect(msg).toBe("A group with this name already exists.")
  })

  it("falls back to generic copy for an unmatched status", () => {
    const msg = apiErrorMessage(new ApiError(500, "boom"), { 409: "conflict copy" })
    expect(msg).toBe("Something went wrong — please try again.")
  })

  it("reports a network failure when fetch rejects with a TypeError", () => {
    const msg = apiErrorMessage(new TypeError("Failed to fetch"))
    expect(msg).toBe("Could not reach the backend — is the server running?")
  })

  it("falls back to generic copy for unknown errors", () => {
    expect(apiErrorMessage(new Error("weird"))).toBe("Something went wrong — please try again.")
    expect(apiErrorMessage("string error")).toBe("Something went wrong — please try again.")
  })
})
