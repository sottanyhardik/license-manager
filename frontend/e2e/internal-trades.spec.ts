import { expect, test, type Page } from "@playwright/test";

/**
 * Internal trades on licence 5611004885 (MONTY CONFECTIONERY), real backend, read-only.
 *
 * Invoices GST/26-27/021 and SC/2026-27/0001 are confirmed INTERNAL on item SR 1. They are listed
 * for audit, labelled, and excluded from external utilisation. Opt-in (LM_REAL_E2E=1).
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const LICENCE_NUMBER = "5611004885";
const ALL_STATUSES = "is_expired=all&flags__is_null=all";

let session: { cookies: Parameters<import("@playwright/test").BrowserContext["addCookies"]>[0]; origins: { origin: string; localStorage: { name: string; value: string }[] }[] } | null = null;

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

async function restoreSession(page: Page) {
  if (!session) throw new Error("session not captured");
  await page.context().addCookies(session.cookies);
  await page.addInitScript((origins) => {
    const entry = origins.find((o) => o.origin === location.origin);
    for (const item of entry?.localStorage ?? []) localStorage.setItem(item.name, item.value);
  }, session.origins);
}

function watchForProblems(page: Page) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/") && response.status() >= 400) problems.push(`${response.status()} ${url.pathname}`);
  });
  return problems;
}

async function openLicence(page: Page, tab?: string) {
  await page.goto(`/licenses?search=${LICENCE_NUMBER}&${ALL_STATUSES}`, { waitUntil: "domcontentloaded" });
  const row = page.locator("article.license-row").filter({ hasText: LICENCE_NUMBER }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: /^Expand licence/ }).click();
  await expect(page.getByTestId("licence-workspace")).toBeVisible({ timeout: 15_000 });
  if (tab) await page.getByRole("tab", { name: tab }).click();
}

test.describe("internal trades on licence 5611004885", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    await signIn(await context.newPage());
    session = await context.storageState();
    await context.close();
  });

  test.beforeEach(async ({ page }) => {
    await restoreSession(page);
  });

  test("Invoice Details lists both INTERNAL invoices, labelled, and shows the external figures as zero", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, "Items & Balance");
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Open invoice details for SR 1, CIF (USD)" }).click();
    const drawer = page.getByRole("dialog", { name: /Invoice Details/ });
    await expect(drawer).toBeVisible({ timeout: 15_000 });

    await expect(drawer.getByText("GST/26-27/021 · INTERNAL TRADE")).toBeVisible();
    await expect(drawer.getByText("SC/2026-27/0001 · INTERNAL TRADE")).toBeVisible();

    const totals = drawer.getByRole("table", { name: "Totals for invoices" });
    // Both invoices, 169,492.39 each, in the Indian digit grouping the app uses.
    await expect(totals.getByRole("row", { name: /Gross internal sales/ })).toContainText("3,38,984.78");
    await expect(totals.getByRole("row", { name: /Gross external sales/ })).toContainText("0.00");
    await expect(totals.getByRole("row", { name: /External uncovered sales/ })).toContainText("0.00");
    await expect(totals.getByRole("row", { name: /Amount contributing to external utilisation/ })).toContainText("0.00");

    await drawer.getByRole("button", { name: "Show details for invoice GST/26-27/021" }).click();
    await expect(drawer.getByText("INTERNAL TRADE", { exact: true })).toBeVisible();
    await expect(drawer.getByText("Not in the external balance. Internal trades do not reduce the licence.")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("Items & Balance shows SR 1 with its available CIF after internal sales are excluded", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, "Items & Balance");
    const table = page.getByTestId("item-table");
    await expect(table).toBeVisible({ timeout: 15_000 });
    const sr1 = table.locator("tbody tr").filter({ hasText: "Refined Cane Sugar" }).first();
    await expect(sr1).toContainText("1,69,492.39");
    expect(problems).toEqual([]);
  });

  test("Invoices & Sales labels both internal invoices and shows the internal total apart from external sales", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, "Invoices & Sales");
    // Exact match: the summary line "Internal trades, not external" is not a badge.
    await expect(page.getByText("INTERNAL TRADE", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("INTERNAL TRADE", { exact: true })).toHaveCount(2);
    await expect(page.getByText(/Internal trades, not external:/)).toBeVisible();
    await expect(page.getByText("Net purchase − net sale (external trades only)")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("the internal invoices remain in the ledger with their original amounts", async ({ page }) => {
    await openLicence(page, "Invoices & Sales");
    await expect(page.getByText("INTERNAL TRADE", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "GST/26-27/021" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "SC/2026-27/0001" }).first()).toBeVisible();
  });
});
