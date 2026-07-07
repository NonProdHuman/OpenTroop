import { expect, test } from "@playwright/test"
import { manifest } from "./fixtures/seed-manifest"

/**
 * Smoke tests for the dev verification loop (GH-171).
 *
 * Assertions read names/counts from the seed **manifest** (GH-245) — produced by
 * `seed-dev-data --emit-manifest` — so they can never silently drift from what the
 * backend actually seeded. Never hard-code member/event names here; add a field to
 * the manifest instead.
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

  // Spot-check one seeded scout and one seeded adult.
  const scout = manifest.members.sampleScout
  const adult = manifest.members.sampleAdult
  await expect(page.getByText(scout)).toBeVisible()
  await expect(page.getByText(adult)).toBeVisible()

  await page.getByText(scout).first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText(scout)).toBeVisible()
})

test("events list renders and opens an event detail", async ({ page }) => {
  await page.goto("/events")
  await expect(page.getByText(/Events \(\d+\)/)).toBeVisible()

  const event = manifest.events.winterCampout
  await expect(page.getByText(event)).toBeVisible()
  await page.getByText(event).first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText(event)).toBeVisible()
  await expect(sheet.getByText(manifest.locations.campWapiti)).toBeVisible()
})

test("RSVP to an upcoming event reflects the new state", async ({ page }) => {
  await page.goto("/events")
  // The seeded upcoming Troop Meeting (T+7); the Demo Admin has not responded yet.
  await page.getByText(manifest.events.upcomingMeeting).first().click()
  const sheet = page.getByRole("dialog")
  await expect(sheet.getByText("RSVP", { exact: true })).toBeVisible()

  const goingButton = sheet.getByTestId("rsvp-going").first()
  await goingButton.click()
  // Selected state is exposed via a stable data attribute (see rsvp-controls.tsx),
  // not a Tailwind class, so restyling can't break this assertion.
  await expect(goingButton).toHaveAttribute("data-selected", "true")

  // Reload → the persisted RSVP still renders selected.
  await page.reload()
  await page.getByText(manifest.events.upcomingMeeting).first().click()
  await expect(page.getByRole("dialog").getByTestId("rsvp-going").first()).toHaveAttribute(
    "data-selected",
    "true",
  )
})
