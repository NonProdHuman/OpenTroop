import { act, render, renderHook, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { TenantProvider, useActiveTenant } from "./tenant-context"

const STORAGE_KEY = "opentroop.active_tenant"

function wrapper({ children }: { children: React.ReactNode }) {
  return <TenantProvider>{children}</TenantProvider>
}

describe("TenantProvider / useActiveTenant", () => {
  beforeEach(() => {
    localStorage.clear()
    // Reset NEXT_PUBLIC_TENANT_ID between tests
    vi.stubEnv("NEXT_PUBLIC_TENANT_ID", "")
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("starts with an empty activeTenantId when localStorage is empty", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper })
    expect(result.current.activeTenantId).toBe("")
  })

  it("hydrates activeTenantId from localStorage on mount", async () => {
    localStorage.setItem(STORAGE_KEY, "tenant-from-storage")

    const { result } = renderHook(() => useActiveTenant(), { wrapper })

    // useEffect runs after first render; wait for the state update
    await act(async () => {})

    expect(result.current.activeTenantId).toBe("tenant-from-storage")
  })

  it("setActiveTenantId updates the context value", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper })

    act(() => {
      result.current.setActiveTenantId("new-tenant-id")
    })

    expect(result.current.activeTenantId).toBe("new-tenant-id")
  })

  it("setActiveTenantId persists to localStorage", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper })

    act(() => {
      result.current.setActiveTenantId("persisted-id")
    })

    expect(localStorage.getItem(STORAGE_KEY)).toBe("persisted-id")
  })

  it("localStorage value is picked up by a newly mounted component", async () => {
    // Simulate: user selected a tenant in a previous session
    localStorage.setItem(STORAGE_KEY, "remembered-tenant")

    const { result } = renderHook(() => useActiveTenant(), { wrapper })
    await act(async () => {})

    expect(result.current.activeTenantId).toBe("remembered-tenant")
  })

  it("does not overwrite a stored value with empty string on mount", async () => {
    localStorage.setItem(STORAGE_KEY, "existing-tenant")

    const { result } = renderHook(() => useActiveTenant(), { wrapper })
    await act(async () => {})

    // Should still be the stored value, not reset to ""
    expect(result.current.activeTenantId).toBe("existing-tenant")
  })

  it("useActiveTenant returns stable setActiveTenantId reference across renders", () => {
    const { result, rerender } = renderHook(() => useActiveTenant(), { wrapper })

    const firstRef = result.current.setActiveTenantId
    rerender()
    expect(result.current.setActiveTenantId).toBe(firstRef)
  })

  it("provides context value to nested children", () => {
    function Child() {
      const { activeTenantId } = useActiveTenant()
      return <div data-testid="tid">{activeTenantId || "none"}</div>
    }

    render(
      <TenantProvider>
        <Child />
      </TenantProvider>,
    )

    expect(screen.getByTestId("tid")).toHaveTextContent("none")
  })

  it("updating state propagates to all consumers", () => {
    function Display() {
      const { activeTenantId } = useActiveTenant()
      return <span data-testid="display">{activeTenantId}</span>
    }
    function Setter() {
      const { setActiveTenantId } = useActiveTenant()
      return <button onClick={() => setActiveTenantId("shared-id")}>set</button>
    }

    render(
      <TenantProvider>
        <Display />
        <Setter />
      </TenantProvider>,
    )

    act(() => {
      screen.getByRole("button").click()
    })

    expect(screen.getByTestId("display")).toHaveTextContent("shared-id")
  })
})
