import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

/**
 * Mocked-API visual check of /allotments (compact rows + inline record tabs).
 *
 * Default data is test-only. To screenshot real local records, dump
 * `{list, detail: {id: …}, licences: {number: …}, boes: {id: …}}` from the API
 * and set LM_ALLOTMENT_FIXTURE=/path/to/fixture.json. Every non-GET /api
 * request is aborted and asserted absent.
 */
const user = {
  id: 1, username: "visual.operator", first_name: "Visual", last_name: "Operator", is_superuser: false,
  roles: ["ALLOTMENT_MANAGER", "LICENSE_VIEWER", "BOE_VIEWER", "USER_MANAGER"],
};

type Fixture = {
  list: Record<string, unknown> & { results: Record<string, unknown>[] };
  detail: Record<string, unknown>; licences: Record<string, unknown>; boes: Record<string, unknown>;
  ledgers?: Record<string, unknown>; history?: Record<string, Record<string, unknown>>; init?: Record<string, unknown>; available?: Record<string, unknown>;
};

const detailRow = (id: number, licence: string, licenceId: number, qty: string, inr: string) => ({
  id, license_number: licence, license_id: licenceId, serial_number: 3, product_description: "Crude palm oil", qty, cif_fc: "12000.50", cif_inr: inr,
  exporter: "Alpha Exports Private Limited", purchase_status: "GE", is_boe: false,
});
const rows = [
  { id: 7101, invoice: "INV/2026/0412", item_name: "Crude Palm Oil", company_name: "Gamma Agro Industries", port_name: "INMUN1", estimated_arrival_date: "12-10-2026", bl_detail: "MSKU1234567", type: "AT", is_boe: false, is_approved: true, required_quantity: "12500.500", alloted_quantity: "12250.500", balanced_quantity: "250.000", required_value: "1520000.75", allotted_value: "1420000.75", allotted_items_count: 2, allocated_licenses_count: 2, dfia_list: "0310001111, 0310002222", allotment_details: [detailRow(1, "0310001111", 11, "10000.000", "1000000.00"), detailRow(2, "0310002222", 22, "2250.500", "420000.75")] },
  { id: 7102, invoice: "INV/2026/0398", item_name: "Cashew Kernels", company_name: "Beta Foods", port_name: "INNSA1", estimated_arrival_date: "02-10-2026", type: "AT", is_boe: true, is_approved: false, required_quantity: "5000", alloted_quantity: "5000", balanced_quantity: "0", required_value: "880000", allotted_value: "880000", allotted_items_count: 1, allocated_licenses_count: 0, dfia_list: "0310003333", allotment_details: [{ ...detailRow(3, "0310003333", 33, "5000.000", "880000.00"), is_boe: true }] },
  { id: 7103, invoice: "", item_name: "Almonds", company_name: "Nutty Co", port_name: null, estimated_arrival_date: "01-01-2027", type: "AT", is_boe: false, is_approved: false, required_quantity: "99", alloted_quantity: "0", balanced_quantity: "99", required_value: "123456.78", allotted_value: "0", allotted_items_count: 0, allocated_licenses_count: 0, dfia_list: "", allotment_details: [] },
];
const builtIn: Fixture = {
  list: {
    count: rows.length, results: rows, current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false,
    list_display: [], form_fields: [], search_fields: ["invoice", "item_name", "company__name"], filter_fields: [],
    filter_config: {
      license_number: { type: "icontains", label: "Licence Number" },
      company: { type: "fk", fk_endpoint: "/masters/companies/", label_field: "name", label: "Company" },
      port: { type: "fk", fk_endpoint: "/masters/ports/", label_field: "name", label: "Port" },
      is_boe: { type: "exact", label: "BOE" },
      is_allotted: { type: "exact", label: "Is Allotted" },
    },
    ordering_fields: [], nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {}, inline_editable: [],
  },
  detail: Object.fromEntries(rows.map((r) => [r.id, { ...r, contact_person: "Ops desk", exchange_rate: "84.50", cif_inr: r.required_value, created_on: "01-09-2026", modified_on: "05-10-2026" }])),
  licences: {
    "0310001111": { results: [{ id: 11, license_number: "0310001111", get_norm_class: "E5", get_balance_cif: "45210.00" }] },
    "0310002222": { results: [{ id: 22, license_number: "0310002222", get_norm_class: "E5", get_balance_cif: "-250.75" }] },
    "0310003333": { results: [{ id: 33, license_number: "0310003333", get_norm_class: "E1", get_balance_cif: "987.32" }] },
  },
  ledgers: {
    11: [{ allotment_number: "ALT-7101", quantity: "10000", cif_fc: "12000.50", outstanding_cif_fc: "12000.50", status: "Approved" }],
    22: [{ allotment_number: "ALT-7101", quantity: "2250.5", cif_fc: "12000.50", outstanding_cif_fc: "12000.50", status: "Approved" }],
    33: [{ allotment_number: "ALT-7102", quantity: "5000", cif_fc: "12000.50", outstanding_cif_fc: "0.00", status: "Linked to BOE" }],
  },
  history: { 7101: { "/api/allotment-actions/7101/": [{ id: 1, username: "visual.operator", action: "CREATE", method: "POST", endpoint: "/api/allotment-actions/7101/allocate-items/", timestamp: "2026-10-05T10:00:00Z", status_code: 201 }] } },
  boes: { 7102: { results: [{ id: 9, bill_of_entry_number: "4521789", bill_of_entry_date: "06-10-2026", port_name: "INNSA1", company_name: "Beta Foods", invoice_no: "INV/2026/0398", total_quantity: "5000", total_fc: "10400", total_inr: "880000", invoice_status_label: "Invoiced" }] } },
};

const fixturePath = process.env.LM_ALLOTMENT_FIXTURE;
const data: Fixture = fixturePath && fs.existsSync(fixturePath) ? JSON.parse(fs.readFileSync(fixturePath, "utf8")) : builtIn;
const listRows = data.list.results;
const plain = listRows.find((r) => !r.is_boe && Array.isArray(r.allotment_details) && (r.allotment_details as unknown[]).length) ?? listRows[0];
const withHistory = listRows.find((r) => Object.values(data.history?.[String(r.id)] ?? {}).some((rows) => Array.isArray(rows) && rows.length)) ?? plain;

async function mockApi(page: Page) {
  const blocked: string[] = [];
  await page.addInitScript((u) => {
    localStorage.setItem("access", "visual-test-access-token");
    localStorage.setItem("refresh", "visual-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const json = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (request.method() !== "GET") { blocked.push(`${request.method()} ${url.pathname}`); return route.abort(); }
    const path = url.pathname.replace(/^\/api\//, "");
    if (path === "auth/me/") return json(user);
    if (path === "allotments/") return json(data.list);
    const detail = path.match(/^allotments\/(\d+)\/$/);
    if (detail) return json(data.detail[detail[1]] ?? listRows.find((r) => String(r.id) === detail[1]) ?? {});
    if (path === "licenses/") return json(data.licences[url.searchParams.get("license_number") ?? ""] ?? { results: [] });
    if (path === "bill-of-entries/") return json(data.boes[url.searchParams.get("allotment") ?? ""] ?? { results: [] });
    const ledger = path.match(/^licenses\/(\d+)\/overview-allotments\/$/);
    if (ledger) return json(data.ledgers?.[ledger[1]] ?? []);
    if (path === "masters/activity-logs/") {
      const prefix = url.searchParams.get("endpoint_prefix") ?? "";
      const id = prefix.match(/\/(\d+)\/$/)?.[1] ?? "";
      return json(data.history?.[id]?.[prefix] ?? []);
    }
    const init = path.match(/^allotment-actions\/(\d+)\/allocation-initialization\/$/);
    if (init) return json(data.init?.[init[1]] ?? {});
    const available = path.match(/^allotment-actions\/(\d+)\/available-licenses\/$/);
    if (available) return json(data.available?.[available[1]] ?? { results: [], count: 0 });
    return json({ results: [], count: 0 });
  });
  return blocked;
}

function watchConsole(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("favicon")) errors.push(m.text()); });
  return errors;
}

const shot = (page: Page, path: string) => page.screenshot({ path, fullPage: true, animations: "disabled" });
const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);

test.describe("allotments workspace visual", () => {
  test("collapsed list, overview, allocation, linked licences and filters at 1440", async ({ page }, testInfo) => {
    const errors = watchConsole(page);
    const blocked = await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("/allotments", { waitUntil: "networkidle" });
    await expect(page.getByRole("list", { name: "Allotments" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Allotments" })).toBeVisible();
    await shot(page, testInfo.outputPath("01-allotments-collapsed.png"));

    const id = String(plain.id);
    await page.getByRole("button", { name: `Expand allotment #${id}`, exact: true }).click();
    const region = page.getByRole("region", { name: `Allotment #${id} details` });
    await expect(region.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await expect(region.getByRole("button", { name: "Allotment", exact: true })).toBeVisible();
    await shot(page, testInfo.outputPath("02-allotment-overview.png"));

    await region.getByRole("tab", { name: "Allocation" }).click();
    await expect(region.getByRole("region", { name: "Allocation records" })).toBeVisible();
    await shot(page, testInfo.outputPath("03-allotment-allocation.png"));

    await region.getByRole("tab", { name: /Allotted Licences/ }).click();
    const allotted = region.getByRole("table", { name: "Allotted licences" });
    await expect(allotted.getByRole("link").first()).toBeVisible();
    await expect(allotted.getByText("…")).toHaveCount(0);
    await expect(region.getByRole("button", { name: /Release allocation/ }).first()).toBeVisible();
    await shot(page, testInfo.outputPath("04-allotment-allotted-licences.png"));

    await region.getByRole("tab", { name: "Allocate Licence" }).click();
    await expect(region.locator(".allotment-action-page")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await shot(page, testInfo.outputPath("07-allotment-allocate.png"));

    await page.getByRole("button", { name: `Collapse allotment #${id}`, exact: true }).click();
    await page.getByRole("button", { name: /^Filters/ }).click();
    await expect(page.getByText("Company", { exact: true }).first()).toBeVisible();
    await shot(page, testInfo.outputPath("05-allotments-filters.png"));

    expect(await noOverflow(page)).toBeFalsy();
    expect(errors).toEqual([]);
    expect(blocked).toEqual([]);
  });

  test("BOE-linked allotment shows its BOE tab", async ({ page }, testInfo) => {
    const boe = listRows.find((r) => r.is_boe && data.boes[String(r.id)]);
    test.skip(!boe, "fixture has no BOE-linked allotment");
    const errors = watchConsole(page);
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("/allotments", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: `Expand allotment #${boe!.id}`, exact: true }).click();
    const region = page.getByRole("region", { name: `Allotment #${boe!.id} details` });
    await region.getByRole("tab", { name: "BOE" }).click();
    await expect(region.getByRole("table")).toBeVisible();
    await shot(page, testInfo.outputPath("06-allotment-boe.png"));
    expect(errors).toEqual([]);
  });

  test("history merges record edits and allocation actions", async ({ page }, testInfo) => {
    const errors = watchConsole(page);
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("/allotments", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: `Expand allotment #${withHistory.id}`, exact: true }).click();
    const region = page.getByRole("region", { name: `Allotment #${withHistory.id} details` });
    await region.getByRole("tab", { name: "History" }).click();
    await expect(region.getByText(/Allocated to licence|Allocation released|Edited/).first()).toBeVisible();
    await shot(page, testInfo.outputPath("08-allotment-history.png"));
    expect(errors).toEqual([]);
  });

  for (const size of [{ name: "768", width: 768, height: 1024 }, { name: "390", width: 390, height: 844 }]) {
    test(`responsive ${size.name}`, async ({ page }, testInfo) => {
      const errors = watchConsole(page);
      await mockApi(page);
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto("/allotments", { waitUntil: "networkidle" });
      await page.getByRole("button", { name: `Expand allotment #${plain.id}`, exact: true }).click();
      await expect(page.getByRole("region", { name: `Allotment #${plain.id} details` })).toBeVisible();
      await shot(page, testInfo.outputPath(`allotments-${size.name}.png`));
      expect(await noOverflow(page)).toBeFalsy();
      expect(errors).toEqual([]);
    });
  }
});
