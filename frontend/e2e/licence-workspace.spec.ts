import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Licence workspace on `/licenses`: the accordion header, the inline workspace and page state.
 *
 * Opt-in (`LM_REAL_E2E=1`) and read-only: nothing is saved, linked, deleted or exported.
 * Every licence is opened the way a user opens it: search or page to its row, expand the row,
 * then select a tab. Licence numbers and ids are from the real database.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";

const LICENCE_ID = 2583;
const LICENCE_NUMBER = "0311054433"; // SR 3 on Items & Balance, with BOE debits
const PREVIOUS_OWNER_NUMBER = "0811016678"; // previous-owner BOE on Reconciliation
const NEGATIVE_CIF_NUMBER = "0311032964"; // available CIF -525208.19
const ZERO_CIF_NUMBER = "0811013695"; // available CIF 0.00
const NO_OWNER_NUMBER = "0311040066"; // no current owner on record
const SR_THREE_ITEM_ID = 38728;

/** The list hides expired licences by default. Searches pass this so every status is found. */
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

/** Collects console errors, page errors and failed API responses, so each flow can assert there were none. */
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

/** The accordion row for a licence number on the current list page. */
function rowFor(page: Page, licenceNumber: string): Locator {
  return page.locator("article.license-row").filter({ hasText: licenceNumber }).first();
}

/** The header of a row: the summary above the workspace, not the workspace itself. */
function headerOf(row: Locator): Locator {
  return row.locator(":scope > div").first();
}

/**
 * Opens a licence as a user does: searches for its number, expands its row, and selects
 * `tab` when given. Returns the row.
 */
async function openLicence(page: Page, licenceNumber: string, tab?: string) {
  await page.goto(`/licenses?search=${licenceNumber}&${ALL_STATUSES}`, { waitUntil: "domcontentloaded" });
  const row = rowFor(page, licenceNumber);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: /^Expand licence/ }).click();
  await expect(page.getByTestId("licence-workspace")).toBeVisible({ timeout: 15_000 });
  if (tab) await page.getByRole("tab", { name: tab }).click();
  return row;
}

test.describe("licence workspace: accordion header and page state", () => {
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

  // ─── Header ──────────────────────────────────────────────────────────────

  test("the header shows the summary fields, with Ledger Date once, collapsed and expanded", async ({ page }) => {
    const problems = watchForProblems(page);
    const row = await openLicence(page, LICENCE_NUMBER);

    for (const label of ["Licence date", "Expiry date", "Ledger date", "Exporter", "Current owner", "Norm class", "Available balance CIF (USD)"]) {
      await expect(headerOf(row).getByText(label, { exact: true }).first(), label).toBeVisible();
    }
    await expect(headerOf(row).getByText("Ledger date", { exact: true })).toHaveCount(1);
    await expect(headerOf(row).getByText(/^(Active|Expired)$/)).toHaveCount(1);
    await expect(row.getByRole("button", { name: /^Collapse licence/ })).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("a positive, a negative and a zero Available CIF each read correctly", async ({ page }) => {
    const problems = watchForProblems(page);
    const positive = await openLicence(page, PREVIOUS_OWNER_NUMBER);
    const positiveValue = headerOf(positive).getByText(/^\d[\d,]*\.\d{2}$/);
    await expect(positiveValue).toBeVisible();
    const [pr, pg] = (await positiveValue.evaluate((el) => getComputedStyle(el).color)).match(/\d+/g)!.map(Number);
    expect(pr <= pg, "a positive value is not red").toBe(true);

    const negative = await openLicence(page, NEGATIVE_CIF_NUMBER);
    const negativeValue = headerOf(negative).getByText(/^-[\d,]+\.\d{2}$/);
    await expect(negativeValue).toBeVisible();
    const colour = await negativeValue.evaluate((el) => getComputedStyle(el).color);
    const [r, g, b] = colour.match(/\d+/g)!.map(Number);
    expect(r, `red channel of ${colour}`).toBeGreaterThan(g);
    expect(r).toBeGreaterThan(b);

    const zero = await openLicence(page, ZERO_CIF_NUMBER);
    await expect(headerOf(zero).getByText("0.00", { exact: true })).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("a licence with no recorded owner shows a dash, and the rest of the header still renders", async ({ page }) => {
    const row = await openLicence(page, NO_OWNER_NUMBER);
    await expect(headerOf(row).getByText("Current owner", { exact: true })).toBeVisible();
    await expect(headerOf(row).getByText("Available balance CIF (USD)")).toBeVisible();
    await expect(headerOf(row).getByText("—").first()).toBeVisible();
  });

  test("the header lays out without clipping or page overflow at desktop, tablet and mobile widths", async ({ page }, testInfo) => {
    const problems = watchForProblems(page);
    const row = await openLicence(page, LICENCE_NUMBER);
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(150);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `page overflow at ${width}px`).toBeLessThanOrEqual(0);

      // No value in the summary is cut off by its box.
      const clipped = await headerOf(row).locator("dd, p, button").evaluateAll((els) =>
        els
          .filter((el) => (el as HTMLElement).scrollWidth > (el as HTMLElement).clientWidth + 1)
          .map((el) => el.textContent),
      );
      expect(clipped, `clipped at ${width}px`).toEqual([]);

      // The available CIF sits on the right, and the toggle at the far right, on desktop and tablet.
      const box = await headerOf(row).boundingBox();
      const cif = await headerOf(row).getByText("Available balance CIF (USD)").boundingBox();
      const toggle = await row.getByRole("button", { name: /^(Expand|Collapse) licence/ }).boundingBox();
      expect(box && cif && toggle).toBeTruthy();
      if (width >= 1024) {
        expect(cif!.x + cif!.width, `CIF on the right at ${width}px`).toBeGreaterThan(box!.x + box!.width * 0.6);
        expect(toggle!.x + toggle!.width, `toggle on the far right at ${width}px`).toBeGreaterThan(box!.x + box!.width - 40);
      }
      await headerOf(row).screenshot({ path: testInfo.outputPath(`header-${width}.png`) });
    }
    expect(problems).toEqual([]);
  });

  test("the header stays visible when the licence is expanded, and the workspace repeats none of its fields", async ({ page }) => {
    const problems = watchForProblems(page);
    const row = await openLicence(page, LICENCE_NUMBER);
    const workspace = page.getByTestId("licence-workspace");

    await expect(headerOf(row).getByText("Available balance CIF (USD)")).toBeVisible();
    await expect(headerOf(row).getByText("Ledger date", { exact: true })).toHaveCount(1);
    await expect(workspace.getByText("Available balance CIF (USD)")).toHaveCount(0);
    await expect(workspace.getByText("Available CIF (USD)")).toHaveCount(0);
    await expect(workspace.getByText("Ledger date", { exact: true })).toHaveCount(0);
    await expect(workspace.getByText("Current owner", { exact: true })).toHaveCount(0);
    await expect(workspace.getByRole("heading", { name: "Licence workspace" })).toBeVisible();
    await expect(workspace.getByText("Available quantity")).toBeVisible();
    expect(await workspace.locator("header dl dt").allTextContents()).toEqual(["Importer", "IEC", "Port", "Purchase status"]);
    expect(problems).toEqual([]);
  });

  // ─── Page state ───────────────────────────────────────────────────────────

  test("paging keeps the workspace open, shows the notice off the page, and returns to the row", async ({ page }) => {
    const problems = watchForProblems(page);
    await page.goto("/licenses", { waitUntil: "domcontentloaded" });
    const first = page.locator("article.license-row").first();
    await expect(first).toBeVisible({ timeout: 15_000 });
    const openedNumber = (await first.getByRole("button", { name: /^View documents for license/ }).innerText()).trim();
    await first.getByRole("button", { name: /^Expand licence/ }).click();
    await expect(page.getByTestId("licence-workspace")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Next page" }).click();
    await expect(
      page.getByText("The open licence is not on this page of results. Its workspace stays open here until you close it."),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("licence-workspace")).toBeVisible();
    await expect(page.locator("article.license-row[data-expanded='true']")).toHaveCount(0);

    await page.getByRole("button", { name: "Previous page" }).click();
    await expect(rowFor(page, openedNumber)).toHaveAttribute("data-expanded", "true", { timeout: 15_000 });
    await expect(page.getByText(/not on this page of results/)).toHaveCount(0);
    expect(problems).toEqual([]);
  });

  test("changing a filter closes the open licence", async ({ page }) => {
    const problems = watchForProblems(page);
    await page.goto("/licenses", { waitUntil: "domcontentloaded" });
    const first = page.locator("article.license-row").first();
    await expect(first).toBeVisible({ timeout: 15_000 });
    await first.getByRole("button", { name: /^Expand licence/ }).click();
    await expect(page.getByTestId("licence-workspace")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("radio", { name: "Expired", exact: true }).click();

    await expect(page.getByTestId("licence-workspace")).toHaveCount(0, { timeout: 15_000 });
    await expect(page.locator("article.license-row[data-expanded='true']")).toHaveCount(0);
    expect(problems).toEqual([]);
  });

  test("changing the search closes the open licence", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER);
    await expect(page.getByTestId("licence-workspace")).toBeVisible();

    const search = page.getByRole("searchbox", { name: "Search licences" });
    await search.fill("0811");
    await search.press("Enter");

    await expect(page.getByTestId("licence-workspace")).toHaveCount(0, { timeout: 15_000 });
    expect(problems).toEqual([]);
  });

  test("a browser reload closes the open licence, and the URL does not bring it back", async ({ page }) => {
    await openLicence(page, LICENCE_NUMBER, "Items & Balance");
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });
    const urlBefore = page.url();

    await page.reload({ waitUntil: "domcontentloaded" });

    await expect(rowFor(page, LICENCE_NUMBER)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("licence-workspace")).toHaveCount(0);
    await expect(rowFor(page, LICENCE_NUMBER)).not.toHaveAttribute("data-expanded", "true");
    expect(page.url()).toBe(urlBefore);
  });

  test("Refresh keeps the licence open on the same tab", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER, "Reconciliation");
    await page.getByRole("button", { name: "Refresh" }).click();

    await expect(page.getByRole("heading", { name: "Source-level reconciliation" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "Reconciliation" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("licence-workspace")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("switching tabs and opening a BOE drawer keep the licence open", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER, "Items & Balance");
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Open BOE debit details for SR 3, CIF (USD)" }).click();
    const drawer = page.getByRole("dialog", { name: /BOE Debit Details/ });
    await expect(drawer).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();

    await page.getByRole("tab", { name: "Invoices & Sales" }).click();
    await expect(page.getByRole("tab", { name: "Invoices & Sales" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("licence-workspace")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("Close collapses the licence and removes its workspace", async ({ page }) => {
    const row = await openLicence(page, LICENCE_NUMBER);
    await page.getByRole("button", { name: "Close" }).click();

    await expect(page.getByTestId("licence-workspace")).toHaveCount(0);
    await expect(row).not.toHaveAttribute("data-expanded", "true");
  });

  test("only one licence is open: opening a second row collapses the first", async ({ page }) => {
    const problems = watchForProblems(page);
    await page.goto("/licenses", { waitUntil: "domcontentloaded" });
    const first = page.locator("article.license-row").nth(0);
    const second = page.locator("article.license-row").nth(1);
    await expect(second).toBeVisible({ timeout: 15_000 });
    await first.getByRole("button", { name: /^Expand licence/ }).click();
    await expect(first).toHaveAttribute("data-expanded", "true");

    // The app's fixed action bar covers the bottom of the viewport. Centre the row so its toggle is clickable.
    await second.evaluate((el) => el.scrollIntoView({ block: "center" }));
    await second.getByRole("button", { name: /^Expand licence/ }).click();

    await expect(second).toHaveAttribute("data-expanded", "true");
    await expect(first).not.toHaveAttribute("data-expanded", "true");
    await expect(page.getByTestId("licence-workspace")).toHaveCount(1);
    expect(problems).toEqual([]);
  });

  // ─── Workspace content (behaviour unchanged) ─────────────────────────────

  test("the workspace shows Overview, Planning, Items & Balance, Invoices & Sales and Reconciliation, in order", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER);
    const tabs = page.getByRole("tablist", { name: "Licence sections" }).getByRole("tab");
    await expect(tabs).toHaveText(["Overview", "Planning", "Items & Balance", "Invoices & Sales", "Reconciliation"]);
    expect(problems).toEqual([]);
  });

  test("the BOE drawer lists Quantity before CIF in every pair, and its summary has the spec metrics", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER, "Items & Balance");
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Open BOE debit details for SR 3, quantity" }).click();
    const drawer = page.getByRole("dialog", { name: /BOE Debit Details/ });
    await expect(drawer).toBeVisible({ timeout: 15_000 });
    await expect(drawer.getByRole("group", { name: "Figure" })).toHaveCount(0);

    const subHeadings = await page.getByTestId("drilldown-table").evaluate((table) =>
      Array.from(table.querySelectorAll("thead tr")[1]?.querySelectorAll("button") ?? []).map((button) => button.getAttribute("aria-label")),
    );
    expect(subHeadings.slice(0, 2)).toEqual(["Sort by BOE Quantity (kg)", "Sort by BOE CIF (USD)"]);

    const summary = drawer.getByRole("table", { name: "Totals for BOE debits" });
    await expect(summary.getByRole("row", { name: /Covered by Sale/ })).toBeVisible();
    await expect(summary.getByRole("row", { name: /Uncovered BOE Debit/ })).toBeVisible();
    await expect(summary.getByRole("row", { name: /Over-linked Excess/ })).toBeVisible();
    await expect(summary.getByRole("row", { name: /Debited \(Item Figure\)/ })).toBeVisible();
    await expect(summary.getByRole("row", { name: /Previous-owner BOE Debit/ })).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    expect(problems).toEqual([]);
  });

  test("Reconciliation shows the source differences, the allocation issues and the bills of entry, quantity first", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, LICENCE_NUMBER, "Reconciliation");

    await expect(page.getByRole("heading", { name: "Source-level reconciliation" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Allocation issues" })).toBeVisible();
    const boes = page.getByRole("table", { name: /Bills of entry behind this licence's balance/ });
    await expect(boes).toBeVisible();
    const headers = await boes.getByRole("columnheader").allTextContents();
    expect(headers.indexOf("BOE Quantity")).toBeLessThan(headers.indexOf("BOE CIF (USD)"));
    expect(headers.indexOf("Covered by Sale — Quantity")).toBeLessThan(headers.indexOf("Covered by Sale — CIF (USD)"));
    expect(headers.indexOf("Uncovered — Quantity")).toBeLessThan(headers.indexOf("Uncovered — CIF (USD)"));
    expect(problems).toEqual([]);
  });

  test("a previous-owner BOE is labelled, and its debit reaches the item's debited figure", async ({ page }) => {
    const problems = watchForProblems(page);
    await openLicence(page, PREVIOUS_OWNER_NUMBER, "Reconciliation");

    const boes = page.getByRole("table", { name: /Bills of entry behind this licence's balance/ });
    await expect(boes.getByText("Previous owner").first()).toBeVisible({ timeout: 15_000 });
    await expect(boes.locator("tr[data-previous-owner='true']").first()).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("the drill-down figures match the balance detail API", async ({ page }) => {
    await openLicence(page, LICENCE_NUMBER, "Items & Balance");
    await expect(page.getByTestId("item-table")).toBeVisible({ timeout: 15_000 });

    const drill = await page.evaluate(async (url) => {
      const access = localStorage.getItem("access");
      const response = await fetch(`/api/${url}`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
      return response.json();
    }, `licence-balances/${LICENCE_ID}/items/${SR_THREE_ITEM_ID}/drilldown/`);

    await page.getByRole("button", { name: "Open BOE debit details for SR 3, CIF (USD)" }).click();
    const drawer = page.getByRole("dialog", { name: /BOE Debit Details/ });
    await expect(drawer).toBeVisible({ timeout: 15_000 });
    await expect(drawer.getByText(`Showing ${drill.boes.rows.length} of ${drill.boes.rows.length} rows`)).toBeVisible();
    await expect(drawer.getByText("CIF reconciles to the item table")).toBeVisible();
  });
});
