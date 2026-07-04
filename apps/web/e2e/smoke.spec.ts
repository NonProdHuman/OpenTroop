import { expect, test } from "@playwright/test"

/**
 * Smoke tests for the dev verification loop (GH-171).
 *
 * These assert against the deterministic dataset created by
 * `uv run seed-dev-data` (backend/scripts/seed_dev_data.py) — member and event
 * names here must stay in sync with that script's fixed dataset.
 */

test("signed-in user lands on the tenant dashboard", async ({ page }) => {
  await page.goto("/")
  // The sidebar renders permission-gated nav — Events is a top-level link the
  // Demo Admin always has.
  await expect(page.getByRole("link", { name: "Events" })).toBeVisible()
})

test("roster lists seeded members and opens a member detail", async ({ page }) => {
  await page.goto("/members")
  await expect(page.getByText(/Members \(\d+\)/)).toBeVisible()

  // 20 scouts + 16 adults seeded; spot-check one of each.
  await expect(page.getByText("Aiden Brooks")).toBeVisible()
  await expect(page.getByText("Sarah Rivers")).toBeVisible()

  await page.getByText("Aiden Brooks").first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText("Aiden Brooks")).toBeVisible()
})

test("events list renders and opens an event detail", async ({ page }) => {
  await page.goto("/events")
  await expect(page.getByText(/Events \(\d+\)/)).toBeVisible()

  await expect(page.getByText("Winter Campout")).toBeVisible()
  await page.getByText("Winter Campout").first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText("Winter Campout")).toBeVisible()
  await expect(sheet.getByText("Camp Wapiti")).toBeVisible()
})

test("RSVP to an upcoming event reflects the new state", async ({ page }) => {
  await page.goto("/events")
  // The seeded upcoming Troop Meeting (T+7); the Demo Admin has not responded yet.
  await page.getByText("Troop Meeting").first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText("RSVP", { exact: true })).toBeVisible()

  const goingButton = sheet.getByRole("button", { name: "Going", exact: true }).first()
  await goingButton.click()
  // Selected state renders with the solid green fill (see rsvp-controls.tsx).
  await expect(goingButton).toHaveClass(/bg-green-600/)

  // Reload → the persisted RSVP still renders selected.
  await page.reload()
  await page.getByText("Troop Meeting").first().click()
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Going", exact: true }).first(),
  ).toHaveClass(/bg-green-600/)
})
