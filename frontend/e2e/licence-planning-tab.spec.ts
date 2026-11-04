import { expect, test, type Page, type Response } from "@playwright/test";

/**
 * Planning tab inside the Licence Workspace, live data. Read-only. Opt in with LM_REAL_E2E=1.
 *
 * 0311054050 has three active plan lines and a positive canonical balance. 0311053224 has five plan lines and
 * a negative canonical balance, which the Planning summary must show rather than floor to zero.
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

/** The licence's workspace, opened on its list row. Resolves to the workspace locator. */
async function openWorkspace(page: Page, licenceNumber: string) {
  await page.goto(`/licenses?search=${licenceNumber}&${ALL_STATUSES}`, { waitUntil: "domcontentloaded" });
  const row = page.locator("article.license-row").filter({ hasText: licenceNumber }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: /^Expand licence/ }).click();
  const workspace = page.getByTestId("licence-workspace");
  await expect(workspace).toBeVisible({ timeout: 15_000 });
  return workspace;
}

/** The displayed amount's leading decimal, with Indian grouping and sign. */
function displayed(text: string): number {
  const match = text.match(/-?[\d,]+(?:\.\d+)?/);
  if (!match) throw new Error(`no figure in "${text}"`);
  return Number(match[0].replace(/,/g, ""));
}

test.describe("Planning tab in the Licence Workspace", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");

  test("Planning sits after Overview, loads this licence's plan records, and shows the canonical balance", async ({ page }) => {
    await signIn(page);
    const licenseDetail = page.waitForResponse(
      (r: Response) => /\/api\/licenses\/\d+\/$/.test(new URL(r.url()).pathname) && r.status() === 200,
      { timeout: 20_000 },
    );
    const workspace = await openWorkspace(page, "0311054050");

    const tabs = workspace.getByRole("tablist", { name: "Licence sections" }).getByRole("tab");
    await expect(tabs).toHaveText(["Overview", "Planning", "Items & Balance", "Invoices & Sales", "Reconciliation"]);

    // Armed just before the tab opens, and matched on this licence's own filter.
    const planRecords = page.waitForResponse(
      (r: Response) => {
        const url = new URL(r.url());
        return url.pathname.endsWith("/license-item-plans/") && url.searchParams.has("license") && r.status() === 200;
      },
      { timeout: 20_000 },
    );
    await workspace.getByRole("tab", { name: "Planning" }).click();
    const body = await (await planRecords).json();
    // The endpoint is paginated: the plan records are in `results`.
    const records: Array<{ planning_item_name: string }> = Array.isArray(body) ? body : body.results;
    const detail = await (await licenseDetail).json();
    expect(records.length).toBeGreaterThan(0);
    for (const record of records) {
      await expect(workspace.getByText(record.planning_item_name).first()).toBeVisible({ timeout: 15_000 });
    }

    // The balance on the Planning summary is the canonical available CIF, not a separate figure.
    const actual = workspace.getByText("Actual Balance CIF", { exact: true }).locator("xpath=..");
    await expect(actual).toBeVisible();
    expect(displayed(await actual.innerText())).toBeCloseTo(Number(detail.operational_reconciliation.actual_balance_cif), 2);
  });

  test("switching between Planning and Items & Balance keeps the same licence; a reload closes the licence as before", async ({ page }) => {
    await signIn(page);
    const workspace = await openWorkspace(page, "0311054050");
    await workspace.getByRole("tab", { name: "Planning" }).click();
    await expect(workspace.getByRole("tab", { name: "Planning" })).toHaveAttribute("aria-selected", "true");

    await workspace.getByRole("tab", { name: "Items & Balance" }).click();
    await expect(workspace.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });
    await workspace.getByRole("tab", { name: "Planning" }).click();
    await expect(workspace.getByText("Actual Balance CIF", { exact: true })).toBeVisible({ timeout: 15_000 });

    // A browser reload closes the open licence (the approved transient-state rule, see the licence workspace spec).
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("licence-workspace")).toHaveCount(0);
  });

  test("a negative canonical balance is shown as a deficit, not floored to zero", async ({ page }) => {
    await signIn(page);
    const licenseDetail = page.waitForResponse(
      (r: Response) => /\/api\/licenses\/\d+\/$/.test(new URL(r.url()).pathname) && r.status() === 200,
      { timeout: 20_000 },
    );
    const workspace = await openWorkspace(page, "0311053224");
    await workspace.getByRole("tab", { name: "Planning" }).click();
    const detail = await (await licenseDetail).json();

    expect(Number(detail.operational_reconciliation.final_balance_cif)).toBeLessThan(0);
    const final = workspace.getByText("Final Balance CIF", { exact: true }).locator("xpath=..");
    await expect(final).toBeVisible({ timeout: 15_000 });
    expect(displayed(await final.innerText())).toBeCloseTo(Number(detail.operational_reconciliation.final_balance_cif), 2);
  });
});
