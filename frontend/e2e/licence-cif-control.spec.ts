import { expect, test, type Page, type Response } from "@playwright/test";

/**
 * Licence-level CIF control on real data. Read-only. Opt in with LM_REAL_E2E=1.
 *
 * 0311051362 has Individual Item CIF OFF. Every item row shows the licence's own available CIF, taken from
 * the canonical detail payload the page loads, and labelled "Licence-level CIF control". The expected
 * value is read from that payload, never hardcoded.
 * 2411004858 has Individual Item CIF ON. Each row keeps its own item-level CIF, so an over-utilised item is badged.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const ALL_STATUSES = "is_expired=all&flags__is_null=all";

/** The Items & Balance column order, 0-based. Quantity comes before CIF in every group. */
const COL = { SR: 0, ORIGINAL_QTY: 4, RESERVED_CIF: 9, INVOICED_CIF: 11, AVAILABLE_QTY: 12, AVAILABLE_CIF: 13, CIF_CONTROL: 14, STATUS: 15 } as const;

/** The visible label for each backend status, as the Status column shows it. */
const STATUS_LABEL: Record<string, string> = {
  RECONCILED: "Reconciled",
  "REVIEW REQUIRED": "Review required",
  "OVER-UTILISED": "Over-utilised",
};

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

/** Opens the licence's Items & Balance tab. Resolves to the workspace and the detail payload the page loaded. */
async function openItemsAndBalance(page: Page, licenceNumber: string) {
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
  await workspace.getByRole("tab", { name: "Items & Balance" }).click();
  const detail = await (await detailLoaded).json();
  return { workspace, detail };
}

/** The leading decimal of a displayed figure (Indian grouping and sign allowed), as a number. A unit suffix such as " kg" is ignored. */
function parseDisplayed(text: string): number {
  const match = text.trim().match(/-?[\d,]+(?:\.\d+)?/);
  if (!match) throw new Error(`no figure in "${text}"`);
  return Number(match[0].replace(/,/g, ""));
}

test.describe("licence-level CIF control", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");

  test("OFF licence 0311051362: every row shows the same licence balance, labelled, and quantities stay per item", async ({ page }) => {
    await signIn(page);
    const { workspace, detail } = await openItemsAndBalance(page, "0311051362");

    expect(detail.cif_control).toBe("LICENCE");
    const expectedLicenceCif = parseDisplayed(detail.cif.available);
    const rows = workspace.locator('[data-testid="item-table"] tbody tr');
    await expect(rows).toHaveCount(detail.items.length);

    for (let index = 0; index < detail.items.length; index += 1) {
      const row = rows.nth(index);
      const cells = row.locator("td");
      // The same licence balance on every row, never a per-item share and never a sum.
      expect(parseDisplayed(await cells.nth(COL.AVAILABLE_CIF).innerText())).toBe(expectedLicenceCif);
      await expect(cells.nth(COL.CIF_CONTROL)).toHaveText("Licence-level CIF control");
      // Available quantity is this item's own figure.
      const item = detail.items[index];
      expect(parseDisplayed(await cells.nth(COL.AVAILABLE_QTY).innerText())).toBe(Number(item.qty.available));
    }

    // SR 3: the allotment CIF difference is ignored, so Reserved for Customers CIF is the payload's figure (0.00),
    // not the 61.79 difference, and the row is not over-utilised by its CIF. Its status is the payload's status.
    const sr3 = detail.items.findIndex((item: { sr: string }) => item.sr === "3");
    expect(sr3).toBeGreaterThanOrEqual(0);
    expect(parseDisplayed(await rows.nth(sr3).locator("td").nth(COL.RESERVED_CIF).innerText())).toBe(
      Number(detail.items[sr3].cif.allotted),
    );
    await expect(rows.nth(sr3).locator("td").nth(COL.STATUS)).toContainText(STATUS_LABEL[detail.items[sr3].status]);
    await expect(rows.nth(sr3).getByText("Over-utilised", { exact: true })).toHaveCount(0);
    expect(parseDisplayed(await rows.nth(sr3).locator("td").nth(COL.ORIGINAL_QTY).innerText())).toBe(
      Number(detail.items[sr3].qty.original),
    );

    // SR 12 keeps its invoice attribution in the Invoiced CIF column, even though its Available CIF is the licence balance.
    const sr12 = detail.items.findIndex((item: { sr: string }) => item.sr === "12");
    expect(sr12).toBeGreaterThanOrEqual(0);
    expect(parseDisplayed(await rows.nth(sr12).locator("td").nth(COL.INVOICED_CIF).innerText())).toBe(
      Number(detail.items[sr12].cif.invoiced),
    );
  });

  test("ON licence 2411004858: item CIF stays enforced per item", async ({ page }) => {
    await signIn(page);
    const { workspace, detail } = await openItemsAndBalance(page, "2411004858");

    expect(detail.cif_control).toBe("ITEM");
    await expect(workspace.getByText("Licence-level CIF control")).toHaveCount(0);
    await expect(workspace.getByText("Over-utilised", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  });
});
