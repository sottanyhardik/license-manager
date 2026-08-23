import { expect, test, type Page } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

const localUser = {
  id: 1,
  username: "trades.performance",
  first_name: "Trades",
  last_name: "Operator",
  is_superuser: true,
  roles: ["TRADE_MANAGER"],
};

const tradesResponse = {
  count: 2,
  current_page: 1,
  total_pages: 1,
  page_size: 25,
  has_next: false,
  has_previous: false,
  list_display: [],
  form_fields: [],
  search_fields: [],
  filter_fields: [],
  filter_config: {},
  ordering_fields: [],
  nested_field_defs: {},
  nested_list_display: {},
  field_meta: {},
  default_filters: {},
  inline_editable: [],
  results: [
    {
      id: 501,
      direction: "SALE",
      direction_label: "Sale",
      invoice_number: "PERF-SALE-501",
      invoice_date: "2026-08-22",
      from_company_label: "Exporter One",
      to_company_label: "Buyer One",
      total_amount: "1250.50",
      paid_or_received: "0",
      due_amount: "1250.50",
      lines: [{ id: 1, sr_number: 1, description: "Trade item", qty_kg: "100.000", cif_fc: "10.00", cif_inr: "1000.00", amount_inr: "1250.50" }],
      boes: [{ bill_of_entry_number: "BOE-PERF-1" }],
    },
    {
      id: 502,
      direction: "PURCHASE",
      direction_label: "Purchase",
      invoice_number: "PERF-PURCHASE-502",
      invoice_date: "2026-08-22",
      from_company_label: "Supplier One",
      to_company_label: "Importer One",
      total_amount: "900.00",
      paid_or_received: "900.00",
      due_amount: "0",
      lines: [],
      linked_trade_info: { id: 501, type: "sale" },
    },
  ],
};

async function mockTradesApi(page: Page, tradesRequests: string[]) {
  await page.addInitScript((user) => {
    localStorage.setItem("access", "trades-performance-access-token");
    localStorage.setItem("refresh", "trades-performance-refresh-token");
    localStorage.setItem("user", JSON.stringify(user));
  }, localUser);

  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.pathname.endsWith("/auth/me/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(localUser) });
      return;
    }
    if (requestUrl.pathname.endsWith("/trades/")) {
      tradesRequests.push(`${route.request().method()} ${requestUrl.pathname}?${requestUrl.searchParams.toString()}`);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(tradesResponse) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

test.describe("trades request lifecycle and visual performance", () => {
  test("uses one canonical list request per direct navigation, has no browser errors, and stays contained", async ({ page }, testInfo) => {
    const tradesRequests: string[] = [];
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text());
    });
    await mockTradesApi(page, tradesRequests);

    const startedAt = Date.now();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/trades", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Trades" })).toBeVisible();
    await expect(page.getByText("PERF-SALE-501")).toBeVisible();
    await expect(page.getByText("PERF-PURCHASE-502")).toBeVisible();
    const coldLoadMs = Date.now() - startedAt;

    expect(tradesRequests).toEqual(["GET /api/trades/?page=1&page_size=25"]);
    await expectNoDocumentOverflow(page);
    await expectNoBasicSemanticViolations(page);
    await expectNoSeriousOrCriticalAxeViolations(page, "main");
    await page.screenshot({ path: testInfo.outputPath("trades-desktop-populated.png"), fullPage: true });

    // A browser reload deliberately performs one fresh canonical request;
    // this confirms there is no duplicate request within either lifecycle.
    const warmStartedAt = Date.now();
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText("PERF-SALE-501")).toBeVisible();
    const warmLoadMs = Date.now() - warmStartedAt;
    expect(tradesRequests).toEqual([
      "GET /api/trades/?page=1&page_size=25",
      "GET /api/trades/?page=1&page_size=25",
    ]);
    expect(coldLoadMs).toBeGreaterThanOrEqual(0);
    expect(warmLoadMs).toBeGreaterThanOrEqual(0);
    expect(errors).toEqual([]);
  });

  test("keeps the populated route usable at tablet and mobile widths", async ({ page }, testInfo) => {
    const tradesRequests: string[] = [];
    await mockTradesApi(page, tradesRequests);

    for (const viewport of [
      { name: "tablet", width: 768, height: 1024 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/trades", { waitUntil: "networkidle" });
      await expect(page.getByText("PERF-SALE-501")).toBeVisible();
      await expectNoDocumentOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`trades-${viewport.name}-populated.png`), fullPage: true });
    }

    expect(tradesRequests).toHaveLength(2);
  });
});
