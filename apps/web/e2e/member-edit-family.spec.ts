import { expect, test } from "@playwright/test"

/**
 * Regression for the member-edit family picker (issue #109 follow-up).
 *
 * Opening the "Add member…" relationship picker used to yank a long edit page
 * back to the top: the popover is portaled and, while it was positioned
 * document-relative ("absolute"), focus moving to its search input scrolled the
 * still-at-top popup into view. The page jumped up, the anchored dropdown moved
 * out from under the cursor, and picking a relative became impossible. The fix
 * positions popovers viewport-relative ("fixed") so focusing them never scrolls
 * the page.
 *
 * Asserts against the deterministic dataset from `uv run seed-dev-data`
 * (backend/scripts/seed_dev_data.py) — member names here must stay in sync.
 */
test("opening the family picker does not scroll the edit page to the top", async ({ page }) => {
  await page.goto("/members")

  // Open a seeded member and jump into their edit page.
  await page.getByText("Aiden Brooks").first().click()
  const sheet = page.getByRole("dialog")
  await sheet.getByRole("button", { name: /edit/i }).click()

  await expect(page.getByRole("heading", { name: /^Edit —/ })).toBeVisible()

  // The Family section sits well below the fold; scroll its trigger into view.
  const addMember = page.getByRole("button", { name: /Add member…/ })
  await addMember.scrollIntoViewIfNeeded()

  const before = await page.evaluate(() => window.scrollY)
  // Sanity: we are genuinely scrolled down, so a jump-to-top would be observable.
  expect(before).toBeGreaterThan(50)

  await addMember.click()

  // The picker opens and its search input is focused — but the page must not move.
  await expect(page.getByPlaceholder("Search members…")).toBeVisible()
  const after = await page.evaluate(() => window.scrollY)
  expect(after).toBeGreaterThanOrEqual(before - 5)
})
