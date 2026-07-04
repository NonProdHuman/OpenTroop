import { defineConfig, devices } from "@playwright/test"

// Load Clerk keys + e2e credentials from .env.local (same file `pnpm dev` uses).
// Node 20.12+ ships loadEnvFile; missing file is fine — env may come from the shell.
try {
  process.loadEnvFile(".env.local")
} catch {
  // no .env.local — rely on the shell environment (CI)
}

/**
 * E2E smoke tests (GH-171). These run against an ALREADY-RUNNING local stack:
 *
 *   1. ./start.sh                                   (Postgres + backend + web)
 *   2. cd backend && uv run seed-dev-data --email <your-e2e-user> --reset
 *   3. pnpm --filter web e2e
 *
 * Required env (in apps/web/.env.local or the shell):
 *   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY / CLERK_SECRET_KEY — the Clerk dev instance
 *   E2E_CLERK_USER_EMAIL / E2E_CLERK_USER_PASSWORD — a password-strategy test user
 *     in that instance, signed in at least once, matching --email above
 * Optional:
 *   E2E_BASE_URL — defaults to the demo tenant subdomain on the local dev server
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.results",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://demo.localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /global\.setup\.ts/ },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Session cookies persisted by the setup project's one-time sign-in.
        storageState: "e2e/.auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
})
