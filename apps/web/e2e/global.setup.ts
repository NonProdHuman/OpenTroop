import { clerk, clerkSetup } from "@clerk/testing/playwright"
import { test as setup } from "@playwright/test"

const AUTH_FILE = "e2e/.auth/user.json"

/**
 * One-time sign-in for the whole e2e run.
 *
 * `clerkSetup()` mints a Clerk Testing Token (bypasses bot detection) using
 * CLERK_SECRET_KEY; `clerk.signIn` then authenticates the password-strategy
 * test user and we persist the session as Playwright storage state so every
 * spec starts already signed in.
 */
setup("authenticate", async ({ page }) => {
  const email = process.env.E2E_CLERK_USER_EMAIL
  const password = process.env.E2E_CLERK_USER_PASSWORD
  if (!email || !password) {
    throw new Error(
      "E2E_CLERK_USER_EMAIL and E2E_CLERK_USER_PASSWORD must be set (see playwright.config.ts)",
    )
  }

  await clerkSetup()
  // Land anywhere the app shell (and Clerk) loads — the sign-in redirect is fine.
  await page.goto("/")
  await clerk.signIn({
    page,
    signInParams: { strategy: "password", identifier: email, password },
  })
  // Confirm the tenant dashboard actually rendered before trusting the session.
  await page.goto("/")
  await page.getByRole("link", { name: "Events" }).waitFor({ timeout: 15_000 })
  await page.context().storageState({ path: AUTH_FILE })
})
