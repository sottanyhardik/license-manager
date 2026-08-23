import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND WORKFLOW
 *
 * This suite is intentionally opt-in.  `scripts/test/run_data_bearing_browser_e2e.sh`
 * provisions a new database named `test_*`, migrates it, and invokes the
 * isolated-only `seed_browser_2509` command before setting LM_REAL_E2E=1.
 * It must never be run against a shared development database.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const queueInvoice = "E2E-QUEUE-2509";
const primaryInvoice = "E2E-ALLOTMENT-2509";

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

async function authGet<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (url) => {
    const access = localStorage.getItem("access");
    const response = await fetch(`/api/${url}`, {
      headers: access ? { Authorization: `Bearer ${access}` } : {},
    });
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    return response.json();
  }, path);
}

test.describe("isolated data-bearing operational workflows", () => {
  test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");
  test.describe.configure({ mode: "serial" });

  test("authenticates and renders seeded licence, planning, and allotment data", async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => {
      if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text());
    });

    await signIn(page);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.goto("/licenses/2509/overview", { waitUntil: "networkidle" });
    await expect(page.getByText("3411008090", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("E2E ALUMINIUM FOIL 2509", { exact: true }).first()).toBeVisible();
    await expectNoDocumentOverflow(page);

    await page.goto("/allotments/1/allocate", { waitUntil: "networkidle" });
    await expect(page.getByText(`Invoice #${primaryInvoice}`, { exact: false })).toBeVisible();
    // The authoritative allotment description is retained as an active
    // filter.  The redesigned compact toolbar exposes it as a removable chip
    // instead of the former standalone text input.
    await expect(page.getByText("Description: E2E ALUMINIUM FOIL 2509", { exact: true })).toBeVisible();
    await expect(page.getByText("3411008090", { exact: true })).toBeVisible();
    await expectNoDocumentOverflow(page);
    await page.screenshot({ path: testInfo.outputPath("real-primary-allotment.png"), fullPage: true });
    expect(errors).toEqual([]);
  });

  test("real PLAN queue refills from 1–10 to 2–11 and persists the debit", async ({ page }, testInfo) => {
    const consoleErrors: string[] = [];
    const failures: string[] = [];
    page.on("console", message => {
      if (message.type() === "error" && !message.text().includes("favicon")) consoleErrors.push(message.text());
    });
    page.on("requestfailed", request => failures.push(`${request.method()} ${request.url()}`));

    await signIn(page);
    await page.goto("/allotments/2/allocate", { waitUntil: "networkidle" });
    await expect(page.getByText(`Invoice #${queueInvoice}`, { exact: false })).toBeVisible();
    await expect(page.getByText("3411009001", { exact: true })).toBeVisible();
    await expect(page.getByText("3411009010", { exact: true })).toBeVisible();
    await expect(page.getByText("3411009011", { exact: true })).toBeHidden();

    const confirms = page.getByRole("button", { name: "Confirm" });
    const maxButtons = page.getByRole("button", { name: "Max" });
    await maxButtons.nth(0).click();
    await expect(confirms.first()).toBeEnabled();
    await confirms.first().click();
    await expect(page.getByText("Successfully allocated 100.000 from 3411009001").first()).toBeVisible();

    // The number remains once in the authoritative allotted-history table,
    // but is no longer one of the ten actionable queue cards.  The 11th
    // eligible licence is promoted without reloading the document.
    await expect(page.getByText("3411009011", { exact: true })).toBeVisible();
    await expect(page.getByText("Allotted Items")).toBeVisible();
    await expectNoDocumentOverflow(page);

    const persisted = await authGet<{ allotment_details?: Array<{ qty: string; cif_fc: string }> }>(page, "allotments/2/");
    expect(persisted.allotment_details).toHaveLength(1);
    expect(Number(persisted.allotment_details?.[0]?.qty)).toBe(100);
    expect(Number(persisted.allotment_details?.[0]?.cif_fc)).toBe(1000);
    expect(consoleErrors).toEqual([]);
    expect(failures).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("real-queue-refilled.png"), fullPage: true });
  });

  test("PLAN and ACTUAL modes retain the seeded allotment context", async ({ page }) => {
    await signIn(page);
    await page.goto("/allotments/1/allocate", { waitUntil: "networkidle" });
    await expect(page.getByText("PLAN BALANCE MODE", { exact: false })).toBeVisible();
    const debitBasis = page.locator("label:has-text('Debit Based On')").locator("..").locator("select");
    await debitBasis.selectOption("ACTUAL");
    await expect(page.getByText("ACTUAL BALANCE MODE", { exact: false })).toBeVisible();
    await expect(page.getByText("Description: E2E ALUMINIUM FOIL 2509", { exact: true })).toBeVisible();
    await expectNoDocumentOverflow(page);
  });

  test("persisted BOE, purchase, sale, ledger, planning and report routes load without server errors", async ({ page }, testInfo) => {
    const failures: string[] = [];
    const pageErrors: string[] = [];
    page.on("requestfailed", request => failures.push(`${request.method()} ${new URL(request.url()).pathname}`));
    page.on("pageerror", error => pageErrors.push(error.message));
    await signIn(page);

    // These are live frontend routes backed by the seeded local Django API,
    // not mocked responses.  The assertions intentionally keep each page's
    // normal table/empty-state semantics intact.
    for (const [route, evidence] of [
      ["/licenses", "3411008090"],
      ["/planning", "Planning"],
      ["/bill-of-entries", "Bill Of Entries"],
      ["/trades", "Trades"],
      ["/license-ledger", "License Ledger"],
      ["/reports/license-purchase-profit", "Purchase"],
      ["/reports/item-pivot", "Item"],
      ["/reconciliation", "Reconciliation"],
      ["/pdf-viewer", "PDF"],
    ] as const) {
      await page.goto(route, { waitUntil: "networkidle" });
      await expect(page.locator("body")).toContainText(evidence, { timeout: 10_000 });
      if (route === "/trades") {
        // The deterministic isolated seed creates both directions.  Keep this
        // assertion here so the real route smoke cannot pass on a heading-only
        // or empty state after a list/serializer/query change.
        await expect(page.getByText("E2E-PURCHASE-2509", { exact: true })).toBeVisible();
        await expect(page.getByText("E2E-SALE-2509", { exact: true })).toBeVisible();
      }
      await expectNoDocumentOverflow(page);
    }
    expect(pageErrors).toEqual([]);
    expect(failures).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("real-operational-routes.png"), fullPage: true });
  });

  test("seeded populated route is responsive at required compact viewports", async ({ page }, testInfo) => {
    await signIn(page);
    for (const viewport of [
      { name: "mobile-320", width: 320, height: 640 },
      { name: "mobile-375", width: 375, height: 812 },
      { name: "mobile-390", width: 390, height: 844 },
      { name: "landscape-667", width: 667, height: 375 },
      { name: "tablet-768", width: 768, height: 1024 },
      { name: "laptop-1024", width: 1024, height: 768 },
      { name: "desktop-1280", width: 1280, height: 800 },
      { name: "desktop-1440", width: 1440, height: 960 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/allotments/1/allocate", { waitUntil: "networkidle" });
      await expect(page.getByText(`Invoice #${primaryInvoice}`, { exact: false })).toBeVisible();
      await expectNoDocumentOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`real-allotment-${viewport.name}.png`), fullPage: true });
    }
  });
});
