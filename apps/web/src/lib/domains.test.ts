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
