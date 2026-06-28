import { act, render, renderHook, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { TenantProvider, useActiveTenant } from "./tenant-context"

const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value.toString() },
    clear: () => { store = {} },
    removeItem: (key: string) => { delete store[key] },
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock })
Object.defineProperty(global, 'localStorage', { value: localStorageMock })

const STORAGE_KEY = "opentroop.active_tenant"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { useState } from "react"

function Wrapper({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient())
  return (
    <QueryClientProvider client={queryClient}>
      <TenantProvider>{children}</TenantProvider>
    </QueryClientProvider>
  )
}

describe("TenantProvider / useActiveTenant", () => {
  beforeEach(() => {
    window.localStorage.clear()
    // Reset NEXT_PUBLIC_TENANT_ID between tests
    vi.stubEnv("NEXT_PUBLIC_TENANT_ID", "")
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("starts with an empty activeTenantId when window.localStorage is empty", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })
    expect(result.current.activeTenantId).toBe("")
  })

  it("hydrates activeTenantId from window.localStorage on mount", async () => {
    window.localStorage.setItem(STORAGE_KEY, "tenant-from-storage")

    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })

    // useEffect runs after first render; wait for the state update
    await act(async () => {})

    expect(result.current.activeTenantId).toBe("tenant-from-storage")
  })

  it("setActiveTenantId updates the context value", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })

    act(() => {
      result.current.setActiveTenantId("new-tenant-id")
    })

    expect(result.current.activeTenantId).toBe("new-tenant-id")
  })

  it("setActiveTenantId persists to window.localStorage", () => {
    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })

    act(() => {
      result.current.setActiveTenantId("persisted-id")
    })

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("persisted-id")
  })

  it("window.localStorage value is picked up by a newly mounted component", async () => {
    // Simulate: user selected a tenant in a previous session
    window.localStorage.setItem(STORAGE_KEY, "remembered-tenant")

    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })
    await act(async () => {})

    expect(result.current.activeTenantId).toBe("remembered-tenant")
  })

  it("does not overwrite a stored value with empty string on mount", async () => {
    localStorage.setItem(STORAGE_KEY, "existing-tenant")

    const { result } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })
    await act(async () => {})

    // Should still be the stored value, not reset to ""
    expect(result.current.activeTenantId).toBe("existing-tenant")
  })

  it("useActiveTenant returns stable setActiveTenantId reference across renders", () => {
    const { result, rerender } = renderHook(() => useActiveTenant(), { wrapper: Wrapper })

    const firstRef = result.current.setActiveTenantId
    rerender()
    expect(result.current.setActiveTenantId).toBe(firstRef)
  })

  it("provides context value to nested children", () => {
    function Child() {
      const { activeTenantId } = useActiveTenant()
      return <div data-testid="tid">{activeTenantId || "none"}</div>
    }

    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <TenantProvider>
          <Child />
        </TenantProvider>
      </QueryClientProvider>,
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

    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <TenantProvider>
          <Display />
          <Setter />
        </TenantProvider>
      </QueryClientProvider>,
    )

    act(() => {
      screen.getByRole("button").click()
    })

    expect(screen.getByTestId("display")).toHaveTextContent("shared-id")
  })
})
