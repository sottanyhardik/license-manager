import { expect, test, type Page } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

const user = {
  id: 2509,
  username: "trades.operator",
  first_name: "Trades",
  last_name: "Operator",
  is_superuser: true,
  roles: ["TRADE_MANAGER", "TRADE_VIEWER"],
};

const purchase = {
  id: 25091,
  direction: "PURCHASE",
  direction_label: "Purchase",
  invoice_number: "E2E-PURCHASE-2509",
  invoice_date: "2026-08-22",
  license_type_label: "DFIA",
  from_company_label: "E2E Supplier Pvt Ltd",
  to_company_label: "E2E Exporter Pvt Ltd",
  total_amount: "1500.00",
  paid_or_received: "0.00",
  due_amount: "1500.00",
  linked_trade_info: { id: 25092, type: "sale" },
  lines: [{ id: 1, sr_number: 1, description: "E2E aluminium foil", hsn_code: "76071190", qty_kg: "100.000", cif_fc: "1000.000", cif_inr: "89283.100", amount_inr: "1500.00" }],
  boes: [{ bill_of_entry_number: "E2E-BOE-2509" }],
};
const sale = {
  ...purchase,
  id: 25092,
  direction: "SALE",
  direction_label: "Sale",
  invoice_number: "E2E-SALE-2509",
  from_company_label: "E2E Exporter Pvt Ltd",
  to_company_label: "E2E Buyer Pvt Ltd",
  paid_or_received: "1500.00",
  due_amount: "0.00",
  linked_trade_info: { id: 25091, type: "purchase" },
};

const populatedList = {
  results: [purchase, sale], count: 2,
  list_display: [], form_fields: [], search_fields: [], filter_fields: [], filter_config: {}, ordering_fields: [],
  nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {}, inline_editable: [],
};

async function mockTrades(page: Page, response = populatedList, status = 200) {
  await page.addInitScript((authenticatedUser) => {
    localStorage.setItem("access", "isolated-trades-access-token");
    localStorage.setItem("refresh", "isolated-trades-refresh-token");
    localStorage.setItem("user", JSON.stringify(authenticatedUser));
  }, user);
  await page.route((url) => new URL(url).pathname.startsWith("/api/"), async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/auth/me/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(user) });
      return;
    }
    if (pathname.endsWith("/trades/")) {
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(response) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

test.describe("trades route accessibility and responsive mock workflow", () => {
  test("renders grouped multi-item trades without console, network, or viewport defects", async ({ page }, testInfo) => {
    const consoleErrors: string[] = [];
    const requestFailures: string[] = [];
    page.on("console", message => {
      if (message.type() === "error" && !message.text().includes("favicon")) consoleErrors.push(message.text());
    });
    page.on("requestfailed", request => requestFailures.push(`${request.method()} ${new URL(request.url()).pathname}`));
    await mockTrades(page);

    for (const viewport of [
      { name: "desktop-1440", width: 1440, height: 900 },
      { name: "desktop-1280", width: 1280, height: 720 },
      { name: "laptop-1024", width: 1024, height: 768 },
      { name: "tablet-768", width: 768, height: 1024 },
      { name: "mobile-390", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/trades", { waitUntil: "networkidle" });
      await expect(page.getByRole("heading", { name: /trades/i })).toBeVisible();
      const disclosure = page.getByRole("button", { name: /sale.*purchase/i });
      await disclosure.click();
      await expect(page.getByText("E2E-PURCHASE-2509")).toBeVisible();
      await expect(page.getByText("E2E-SALE-2509")).toBeVisible();
      await expectNoBasicSemanticViolations(page);
      if (viewport.name === "desktop-1440" || viewport.name === "mobile-390") {
        await expectNoSeriousOrCriticalAxeViolations(page, "main");
      }
      await expectNoDocumentOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`trades-${viewport.name}.png`), fullPage: true });
    }

    expect(consoleErrors).toEqual([]);
    expect(requestFailures).toEqual([]);
  });

  test("handles a server error and an empty response without retaining populated rows", async ({ page }) => {
    await mockTrades(page, { detail: "Unable to load trades" }, 500);
    await page.goto("/trades", { waitUntil: "networkidle" });
    await expect(page.locator("main").getByText(/unable to load trades|failed to load data/i)).toBeVisible();

    await page.unrouteAll();
    await mockTrades(page, { ...populatedList, results: [], count: 0 });
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText("No trades found")).toBeVisible();
    await expect(page.getByText("E2E-PURCHASE-2509")).toBeHidden();
  });

  test("paired trades have a keyboard-operable disclosure", async ({ page }) => {
    await mockTrades(page);
    await page.goto("/trades", { waitUntil: "networkidle" });
    const disclosure = page.getByRole("button", { name: /sale.*purchase/i });
    await expect(disclosure).toBeVisible();
    await expect(disclosure).toHaveAttribute("aria-expanded", "false");
    await disclosure.focus();
    await page.keyboard.press("Enter");
    await expect(disclosure).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText("E2E-PURCHASE-2509")).toBeVisible();
    await page.keyboard.press("Space");
    await expect(disclosure).toHaveAttribute("aria-expanded", "false");
  });
});
