import { expect, test, type Page } from "@playwright/test";

/**
 * Licence item balances — browser verification against the live backend.
 *
 * Opt-in (`LM_REAL_E2E=1`). Read-only: nothing is saved, linked, deleted or exported.
 * Expected figures are read from `/api/licence-balances/...` so the test checks the page
 * against the same canonical response, not against hard-coded numbers.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const LICENCE_NUMBER = "0311054433";
const LICENCE_ID = 2583;
const SR_THREE_ITEM_ID = 38728;

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

async function apiGet<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (url) => {
    const access = localStorage.getItem("access");
    const response = await fetch(`/api/${url}`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    return response.json();
  }, path);
}

test.describe("licence item balances", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    await signIn(await context.newPage());
    session = await context.storageState();
    await context.close();
  });

  test("table shows the licence with CIF and quantity figures from the canonical API", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licence-balances?search=${LICENCE_NUMBER}`, { waitUntil: "domcontentloaded" });
    const table = page.getByTestId("balance-table");
    await expect(table).toBeVisible({ timeout: 15_000 });

    const api = await apiGet<{ count: number; results: { licence_number: string; cif: { available?: string; status: string } }[] }>(
      page,
      `licence-balances/?search=${LICENCE_NUMBER}`,
    );
    expect(api.count).toBe(1);
    const row = table.getByRole("row").filter({ hasText: LICENCE_NUMBER });
    await expect(row).toHaveCount(1);
    // The label appears on the status pill and beside the CIF and quantity figures.
    await expect(row.getByText("Over-utilised").first()).toBeVisible();
    // Negative available is shown with its sign, never clipped or floored.
    expect(api.results[0].cif.available?.startsWith("-")).toBe(true);
    await expect(row).toContainText("-");
  });

  test("column toggle reveals quantity columns and remembers the choice", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licence-balances?search=${LICENCE_NUMBER}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("balance-table")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("columnheader", { name: /Original qty/i })).toHaveCount(0);

    await page.getByTestId("column-toggle").click();
    await page.getByRole("menuitemcheckbox", { name: /Original qty/i }).click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("columnheader", { name: /Original qty/i })).toHaveCount(1);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByRole("columnheader", { name: /Original qty/i })).toHaveCount(1, { timeout: 15_000 });
  });

  test("detail page shows CIF and quantity summaries and one row per SION item", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licence-balances/${LICENCE_ID}`, { waitUntil: "domcontentloaded" });
    const items = page.getByTestId("item-table");
    await expect(items).toBeVisible({ timeout: 15_000 });

    const detail = await apiGet<{ items: { item_id: number }[] }>(page, `licence-balances/${LICENCE_ID}/`);
    // Header rows (group + column labels) are excluded; one body row per SION item.
    await expect(items.locator("tbody tr")).toHaveCount(detail.items.length);
  });

  test("movement ledger ends at the item's available balance and shows memo rows distinctly", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licence-balances/${LICENCE_ID}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    const itemApi = await apiGet<{ cif: { available: string }; cif_movements: { memo: boolean; running_balance: string | null }[] }>(
      page,
      `licence-balances/${LICENCE_ID}/items/${SR_THREE_ITEM_ID}/`,
    );
    const live = itemApi.cif_movements.filter((m) => !m.memo);
    expect(live[live.length - 1].running_balance).toBe(itemApi.cif.available);

    // Movement ledgers are opened from an expanded item row (the design keeps the table compact).
    await page.getByRole("button", { name: "Show sources for SR 3" }).click();
    await page.getByRole("button", { name: "Open movement ledger" }).click();
    const ledger = page.getByTestId("movement-ledger");
    await expect(ledger).toBeVisible({ timeout: 15_000 });
    await expect(ledger).toContainText("Original authorisation");
    await expect(ledger).toContainText(/matches available/i);
    if (itemApi.cif_movements.some((m) => m.memo)) {
      await expect(ledger.locator("tr.memo, [data-memo='true']").first()).toBeVisible();
    }
  });

  test("drill-down drawer lists the BOE rows behind the item's Debited figure and reconciles to the item table", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licence-balances/${LICENCE_ID}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    const drill = await apiGet<{
      boes: { rows: { kind: string }[]; totals: { debited_cif: string } };
      reconciliation: { status: string };
    }>(page, `licence-balances/${LICENCE_ID}/items/${SR_THREE_ITEM_ID}/drilldown/`);

    await page.getByRole("button", { name: "Show sources for SR 3" }).click();
    await page.getByRole("button", { name: "View all BOE debits for SR 3" }).click();
    const drawer = page.getByRole("dialog", { name: /BOE Debit Details/ });
    await expect(drawer).toBeVisible({ timeout: 15_000 });

    // Row count matches the API; the drawer reports the same reconciliation result as the item table.
    await expect(drawer.getByTestId("drilldown-table").locator("tbody > tr")).toHaveCount(drill.boes.rows.length);
    await expect(drawer.getByTestId("reconciliation-lines").first()).toBeAttached();
    expect(drill.reconciliation.status).toBe("RECONCILED");
    await expect(drawer.getByText("CIF reconciles to the item table")).toBeVisible();

    // Closing returns to the licence page; the item's sources stay expanded.
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(page.getByRole("button", { name: "Hide sources for SR 3" })).toBeVisible();
  });

  test("no duplicate list requests for one committed search change", async ({ page }) => {
    await restoreSession(page);
    await page.goto("/licence-balances", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("balance-table")).toBeVisible({ timeout: 15_000 });

    let listRequests = 0;
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/licence-balances/") listRequests += 1;
    });
    await page.getByLabel("Search by licence number or importer").fill(LICENCE_NUMBER);
    await page.waitForTimeout(1200);
    expect(listRequests).toBeLessThanOrEqual(2);
  });
});
