import { expect, test, type Page } from "@playwright/test";

/**
 * Licence-level CIF control on real data. Read-only. Opt in with LM_REAL_E2E=1.
 *
 * 0311051322 has Individual Item CIF OFF: each item's CIF is attribution ("Licence-level CIF control")
 * and is not badged over-utilised by its own sign. The licence's pooled CIF decides.
 * 2411004858 has Individual Item CIF ON: item CIF is enforced per item, so an over-utilised item is badged.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const ALL_STATUSES = "is_expired=all&flags__is_null=all";

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const username = page.locator("#login-username");
  await expect(username).toBeVisible();
  await expect(async () => {
    await username.fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await expect(username).toHaveValue(process.env.LM_USERNAME || "hardik");
  }).toPass({ timeout: 10_000 });
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function openItemsAndBalance(page: Page, licenceNumber: string) {
  await page.goto(`/licenses?search=${licenceNumber}&${ALL_STATUSES}`, { waitUntil: "domcontentloaded" });
  const row = page.locator("article.license-row").filter({ hasText: licenceNumber }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: /^Expand licence/ }).click();
  const workspace = page.getByTestId("licence-workspace");
  await expect(workspace).toBeVisible({ timeout: 15_000 });
  await workspace.getByRole("tab", { name: "Items & Balance" }).click();
  return workspace;
}

test.describe("licence-level CIF control", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");

  test("OFF licence 0311051322: item CIF is attribution and the item row is not over-utilised", async ({ page }) => {
    await signIn(page);
    const workspace = await openItemsAndBalance(page, "0311051322");

    // SR 3 (Vegetable Shortening) has a negative item CIF of -59,388.22 under licence-level control.
    const sr3 = workspace.locator("tr").filter({ hasText: "Vegetable Shortening" }).first();
    await expect(sr3).toBeVisible({ timeout: 15_000 });
    await expect(sr3.getByText("Licence-level CIF control").first()).toBeVisible();
    await expect(sr3.getByText("Over-utilised", { exact: true })).toHaveCount(0);
    await expect(sr3.getByText("-59,388.22")).toBeVisible();
  });

  test("ON licence 2411004858: item CIF stays enforced per item", async ({ page }) => {
    await signIn(page);
    const workspace = await openItemsAndBalance(page, "2411004858");

    await expect(workspace.getByText("Licence-level CIF control")).toHaveCount(0);
    await expect(workspace.getByText("Over-utilised", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  });
});
