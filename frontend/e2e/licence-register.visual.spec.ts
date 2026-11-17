import { expect, test, type Page } from "@playwright/test";

/**
 * Mocked-API visual check of the /licenses register (collapsed header rows and
 * one expanded record). All data below is test-only; the app code never sees it
 * outside the intercepted /api/ calls.
 */
const user = {
  id: 1,
  username: "visual.operator",
  first_name: "Visual",
  last_name: "Operator",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

const base = {
  exporter_iec: "0301000001", get_norm_class: "E1", individual_item_cif_override: false, latest_transfer: null,
  purchase_status_label: "DFIA", purchase_status_code: "GE", is_manually_planned: false,
  has_tl: true, has_copy: true, has_condition_sheet: false, is_over_utilised: false,
};
const licences = [
  { ...base, id: 1, license_number: "0310123456", license_date: "05-01-2020", license_expiry_date: "04-01-2021", ledger_date: "10-02-2020", port_name: "INNSA1", exporter_name: "Alpha Exports Private Limited", get_balance_cif: "1234.5", latest_transfer: "Transferred to Beta" },
  { ...base, id: 2, license_number: "0310654321", license_date: "15-08-2024", license_expiry_date: "14-08-2099", ledger_date: null, port_name: "INMAA1", exporter_name: "Beta Foods", get_balance_cif: -250.75, is_over_utilised: true, purchase_status_label: "Advance", individual_item_cif_override: true },
  { ...base, id: 3, license_number: "0310777777", license_date: "01-12-2025", license_expiry_date: "30-11-2099", ledger_date: "02-12-2025", port_name: null, exporter_name: null, exporter_iec: null, get_norm_class: null, get_balance_cif: "987654.321", is_manually_planned: true, purchase_status_label: null },
  { ...base, id: 4, license_number: "0310888888", license_date: "01-06-2025", license_expiry_date: "31-05-2099", ledger_date: "02-06-2025", port_name: "INBOM4", exporter_name: "Gamma Agro Industries", get_balance_cif: "45210.00" },
  { ...base, id: 5, license_number: "0310000004", license_date: null, license_expiry_date: null, ledger_date: null, port_name: "INBOM4", exporter_name: "Delta", get_balance_cif: 0 },
];

const ledger = {
  license: {},
  financial_ledger: { rows: [], summary: { has_trading_activity: false, missing_purchase_warning: { show_warning: false, message: "" } } },
  customs_ledger: {
    rows: [],
    summary: { opening_balance: 250000, total_boe_cif: 198765.5, remaining_after_boe: 51234.5, total_pending_allotment_cif: 6024.5, computed_balance: 45210, engine_balance: 45210, difference: 0, mismatched: false, tolerance: 0.01 },
  },
  reconciliation: { financial_ledger_balance: 0, customs_ledger_balance: 0, balance_engine: 0, difference: 0, tolerance: 0.01, matched: true },
  warnings: [],
  timeline: [],
};

async function mockApi(page: Page) {
  await page.addInitScript((u) => {
    localStorage.setItem("access", "visual-test-access-token");
    localStorage.setItem("refresh", "visual-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (path.endsWith("/auth/me/")) return json(user);
    if (path.endsWith("/licenses/")) {
      return json({
        count: licences.length, results: licences, current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false,
        list_display: ["license_number"], form_fields: [], search_fields: ["license_number"], filter_fields: [], filter_config: {},
        ordering_fields: [], nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {}, inline_editable: [],
      });
    }
    if (path.endsWith("/balance-ledger/")) return json(ledger);
    if (path.endsWith("/overview-items/")) return json({ rows: [] });
    if (path.endsWith("/overview-boes/") || path.endsWith("/overview-allotments/")) return json([]);
    return json({ results: [], count: 0 });
  });
}

function watchConsole(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("favicon")) errors.push(m.text());
  });
  return errors;
}

const sizes = [
  { name: "1440", width: 1440, height: 960 },
  { name: "1366", width: 1366, height: 768 },
  { name: "768", width: 768, height: 1024 },
  { name: "390", width: 390, height: 844 },
];

test.describe("licence register visual", () => {
  for (const size of sizes) {
    test(`register collapsed + expanded at ${size.name}`, async ({ page }, testInfo) => {
      const errors = watchConsole(page);
      await mockApi(page);
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto("/licenses", { waitUntil: "networkidle" });
      await expect(page.getByRole("article", { name: "License 0310123456" })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`licences-${size.name}-collapsed.png`), fullPage: true });

      await page.getByRole("button", { name: "Expand license 0310654321" }).click();
      const region = page.getByRole("region", { name: "License 0310654321 details" });
      await expect(region.getByRole("region", { name: "Financial summary" })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`licences-${size.name}-expanded.png`), fullPage: true });

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow).toBeFalsy();
      expect(errors).toEqual([]);
    });
  }

  test("register renders in dark mode at 1440", async ({ page }, testInfo) => {
    const errors = watchConsole(page);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("/licenses", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Expand license 0310654321" }).click();
    await expect(page.getByRole("region", { name: "Financial summary" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("licences-1440-dark.png"), fullPage: true });
    expect(errors).toEqual([]);
  });
});
