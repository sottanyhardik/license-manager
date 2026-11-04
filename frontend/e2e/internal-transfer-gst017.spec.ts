import { expect, test, type Page, type Response } from "@playwright/test";

/**
 * Internal transfer GST/26-27/017 on licence 0311051531, live data. Read-only. Opt in with LM_REAL_E2E=1.
 *
 * The VISION -> LABDHI transfer (sale 633, copied purchase 634, one persisted COPIED pair) is an explicit
 * INTERNAL transfer. Its Items & Balance figures come from the canonical payload, and the Invoices & Sales
 * tab shows the sale and purchase as INTERNAL TRADE, not external utilisation.
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

async function openLicence(page: Page, licenceNumber: string, tab: string) {
  const detailLoaded = page.waitForResponse(
    (response: Response) => /\/api\/licence-balances\/\d+\/$/.test(new URL(response.url()).pathname) && response.status() === 200,
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

test.describe("internal transfer GST/26-27/017", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");

  test("0311051531 SR 1 shows the transfer as no utilisation, and the balance comes from the canonical payload", async ({ page }) => {
    await signIn(page);
    const { workspace, detail } = await openLicence(page, "0311051531", "Items & Balance");

    const sr1 = detail.items.find((item: { sr: string }) => item.sr === "1");
    expect(sr1.cif.invoiced).toBe("0.00");
    expect(sr1.status).toBe("REVIEW REQUIRED");
    expect(sr1.flags).toContain("INTERNAL_TRANSFER_NO_EXTERNAL_SALE");
    // The displayed licence balance is the canonical figure from the payload, on every row.
    const shown = (text: string) => Number(text.trim().match(/-?[\d,]+(?:\.\d+)?/)?.[0].replace(/,/g, ""));
    const rows = workspace.locator('[data-testid="item-table"] tbody tr');
    await expect(rows.first()).toBeVisible();
    expect(shown(await rows.first().locator("td").nth(13).innerText())).toBe(Number(detail.cif.available));
  });

  test("the Invoices & Sales tab labels GST/26-27/017 as an internal transfer", async ({ page }) => {
    await signIn(page);
    const { workspace } = await openLicence(page, "0311051531", "Invoices & Sales");

    // Both sides of the transfer, the sale 633 and the copied purchase 634, carry the INTERNAL TRADE badge.
    await expect(workspace.getByText("INTERNAL TRADE", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
    await expect(workspace.getByText("INTERNAL TRADE", { exact: true })).toHaveCount(2);
  });
});
