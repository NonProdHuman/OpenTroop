import { afterEach, describe, expect, it, vi } from "vitest"

// Regression: protocol() used to hard-default to "https:" on the server while the client
// read window.location.protocol ("http:" in local dev), producing mismatched hrefs and a
// React hydration warning. Server and client must agree on the scheme.
describe("domains protocol()", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("server and client agree on scheme for localhost (no hydration mismatch)", async () => {
    vi.resetModules()
    const client = await import("./domains")
    const clientUrl = client.getLandingUrl("/") // jsdom serves over http

    vi.resetModules()
    vi.stubGlobal("window", undefined) // simulate SSR — no window
    const server = await import("./domains")
    const serverUrl = server.getLandingUrl("/")

    expect(serverUrl).toBe("http://localhost:3000/")
    expect(clientUrl).toBe(serverUrl)
  })

  it("defaults to https on the server for a non-localhost domain", async () => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_APP_DOMAIN", "opentroop.dev")
    vi.stubGlobal("window", undefined)
    const { getAdminUrl, getTenantUrl } = await import("./domains")

    expect(getAdminUrl("/tenants")).toBe("https://admin.opentroop.dev/tenants")
    expect(getTenantUrl("troop123", "/")).toBe("https://troop123.opentroop.dev/")
  })
})

describe("isDemoHost (GH-246)", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("is false when NEXT_PUBLIC_DEMO_HOST is unset (feature off)", async () => {
    vi.resetModules()
    const { isDemoHost } = await import("./domains")
    expect(isDemoHost()).toBe(false)
  })

  it("is true only when the current host matches the configured demo host", async () => {
    // jsdom serves from http://localhost:3000/, so window.location.host is localhost:3000.
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_DEMO_HOST", "localhost:3000")
    const { isDemoHost } = await import("./domains")
    expect(isDemoHost()).toBe(true)
  })

  it("is false when a demo host is configured but does not match the current host", async () => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_DEMO_HOST", "demo.opentroop.dev")
    const { isDemoHost } = await import("./domains")
    expect(isDemoHost()).toBe(false)
  })

  it("is false on the server (no window)", async () => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_DEMO_HOST", "localhost:3000")
    vi.stubGlobal("window", undefined)
    const { isDemoHost } = await import("./domains")
    expect(isDemoHost()).toBe(false)
  })
})
