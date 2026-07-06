import { describe, expect, it, vi } from "vitest"
import { SSO_PROVIDERS, settleSsoFlow } from "./sso"

describe("settleSsoFlow", () => {
  it("activates the created session and reports signed-in", async () => {
    const setActive = vi.fn().mockResolvedValue(undefined)
    await expect(settleSsoFlow({ createdSessionId: "sess_1", setActive })).resolves.toBe(true)
    expect(setActive).toHaveBeenCalledWith({ session: "sess_1" })
  })

  it("reports incomplete when no session was created (MFA / transfer flows)", async () => {
    const setActive = vi.fn()
    await expect(settleSsoFlow({ createdSessionId: null, setActive })).resolves.toBe(false)
    expect(setActive).not.toHaveBeenCalled()
  })

  it("reports incomplete when setActive is unavailable", async () => {
    await expect(
      settleSsoFlow({ createdSessionId: "sess_1", setActive: null }),
    ).resolves.toBe(false)
  })
})

describe("SSO_PROVIDERS", () => {
  it("offers the providers the web chooser offers today (Apple gated on Clerk config)", () => {
    expect(SSO_PROVIDERS.map((p) => p.strategy)).toEqual(["oauth_microsoft", "oauth_google"])
  })
})
