import { expect, test, type Page, type Response } from "@playwright/test";

/**
 * Internal transfer LML/2026-27/0023 on licence 0311049585, live data. Read-only. Opt in with LM_REAL_E2E=1.
 *
 * The sale from LABDHI MERCANTILE LLP to LABDHI GLOBAL LLP and its purchase are one internal transfer. The item's
 * invoiced and available figures come from the canonical payload, and the Invoices & Sales ledger labels both sides.
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

async function openTab(page: Page, licenceNumber: string, tab: string) {
  const detailLoaded = page.waitForResponse(
    (r: Response) => /\/api\/licence-balances\/\d+\/$/.test(new URL(r.url()).pathname) && r.status() === 200,
    { timeout: 20_000 },
  );
  await page.goto(`/licenses?search=${licenceNumber}&${ALL_STATUSES}`, { waitUntil: "domcontentloaded" });
  const row = page.locator("article.license-row").filter({ hasText: licenceNumber }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: /^Expand licence/ }).click();
  const workspace = page.getByTestId("licence-workspace");
  await expect(workspace).toBeVisible({ timeout: 15_000 });
  await workspace.getByRole("tab", { name: tab }).click();
  return { workspace, detail: await (await detailLoaded).json() };
}

test.describe("internal transfer LML/2026-27/0023", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");

  test("Items & Balance shows the item's invoiced and available figures from the canonical payload", async ({ page }) => {
    await signIn(page);
    const { workspace, detail } = await openTab(page, "0311049585", "Items & Balance");

    const item = detail.items.find((row: { sr: string }) => row.sr === "1");
    expect(item.cif.invoiced).toBeDefined();
    const rows = workspace.locator('[data-testid="item-table"] tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    const available = Number((await rows.first().locator("td").nth(13).innerText()).replace(/[,\s]/g, "").match(/-?[\d.]+/)?.[0]);
    expect(available).toBeCloseTo(Number(item.cif.available), 2);
  });

  test("Invoices & Sales labels both sides of LML/2026-27/0023 as an internal transfer, with the counterpart", async ({ page }) => {
    await signIn(page);
    const { workspace } = await openTab(page, "0311049585", "Invoices & Sales");

    await expect(workspace.getByText("INTERNAL TRADE", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
    await expect(workspace.getByText("INTERNAL TRADE", { exact: true })).toHaveCount(2);
    await expect(workspace.getByText(/counterpart LML\/2026-27\/0023 \(purchase, trade 615\)/)).toBeVisible();
    await expect(workspace.getByText(/counterpart LML\/2026-27\/0023 \(sale, trade 614\)/)).toBeVisible();
  });
});
