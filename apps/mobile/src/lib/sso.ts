/**
 * Native SSO sign-in against the shared Clerk instance (the same providers the
 * web app's Clerk chooser offers). Clerk has no hosted-page → native session
 * handoff, so the native pattern is one `useSSO().startSSOFlow()` per provider:
 * the system browser opens, the user authenticates, and the created session is
 * activated in-app.
 *
 * Apple is deliberately absent until it is configured in the Clerk dashboard —
 * note that App Review Guideline 4.8 requires "Sign in with Apple" before an
 * App Store release that offers other social logins, so it must be added as
 * part of iOS release prep (add `oauth_apple` here; nothing else changes).
 */

export type SsoStrategy = "oauth_microsoft" | "oauth_google" | "oauth_apple"

export const SSO_PROVIDERS: readonly { strategy: SsoStrategy; label: string }[] = [
  { strategy: "oauth_microsoft", label: "Continue with Microsoft" },
  { strategy: "oauth_google", label: "Continue with Google" },
]

/** The subset of Clerk's `startSSOFlow()` result that settling needs. */
export interface SsoFlowResult {
  createdSessionId: string | null
  setActive?: ((params: { session: string }) => Promise<void>) | null
}

/**
 * Activate the session a completed SSO flow created. Returns true when the
 * user is signed in; false when Clerk needs more steps (MFA, first-factor
 * transfer) — the caller shows guidance instead of navigating.
 */
export async function settleSsoFlow(result: SsoFlowResult): Promise<boolean> {
  if (!result.createdSessionId || !result.setActive) return false
  await result.setActive({ session: result.createdSessionId })
  return true
}
