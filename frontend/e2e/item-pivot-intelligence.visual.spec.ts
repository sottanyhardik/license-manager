import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

/**
 * Mocked-API visual check of the Item Pivot "Utilization intelligence" views.
 * Set LM_PIVOT_FIXTURE to a JSON dump ({norms, intel: {E5: …}, recs: {E5: {ids, data}}})
 * of the read-only endpoints to screenshot real local data; otherwise a small
 * built-in fixture is used. Every non-GET /api request is aborted and asserted absent.
 */
const user = { id: 1, username: "visual.operator", first_name: "Visual", last_name: "Operator", is_superuser: false, roles: ["REPORT_VIEWER", "LICENSE_MANAGER"] };

const lic = (id: number, number: string, extra = {}) => ({
  license_id: id, license_number: number, sion: "E5", company: "Alpha Foods", expiry_date: "2026-12-31", purchase_status: "GE",
  original_cif: "250000.00", boe_cif: "150000.00", allotment_cif: "10000.00", billed_cif: "0.00", other_adjustments_cif: "0.00",
  available_cif: "90000.00", is_over_utilised: false, components_reconcile: true, planned_cif: "40000.00", final_balance_cif: "50000.00",
  utilisation_percent: "64.0", products: ["ITEM:1:E5"], ...extra,
});
const builtIn = {
  norms: [{ norm_class: "E5", description: "Biscuits" }],
  intel: { E5: {
    overview: { licence_count: 2, original_cif: "500000.00", boe_cif: "300000.00", allotment_cif: "20000.00", billed_cif: "0.00", other_adjustments_cif: "0.00", available_cif: "180000.00", planned_cif: "80000.00", final_balance_cif: "100000.00", utilisation_percent: "64.0", eligible_product_count: 1, underutilised_licence_count: 1, warning_count: 0, attention_product_count: 0, unreconciled_licence_count: 0, status_counts: { UNDERUTILIZED: 1, CORRECT: 1 }, consolidation: { mapped: 1, ambiguous: 0, unmapped: 0, merged_source_records: 2, mapping_review: 0 }, bases: { licence: "Canonical engine", item: "Item-level raw records" } },
    licences: [lic(1, "0310000001"), lic(2, "0310000002")],
    products: [{ key: "ITEM:1:E5", kind: "MAPPED", item_name_id: 1, product: "SUGAR", sion: "E5", mapping_basis: "Master item link", hsn_codes: ["17019990"], aliases: ["Sugar"], hsn_chapters: ["17"], mapping_review: null, eligible_licences: 2, source_record_count: 2, source_records: [], entitlement_qty: "20000", allotted_qty: "1000", debited_qty: "12000", billed_qty: "0", balance_qty: "7000", max_unit_price: "0.60", planned_qty: "3000", planned_cif: "1800.00", utilisation_percent: "65.0", status_counts: { UNDERUTILIZED: 1, CORRECT: 1 } }],
    eligibility: [1, 2].map((id) => ({ license_id: id, license_number: `031000000${id}`, product_key: "ITEM:1:E5", product: "SUGAR", kind: "MAPPED", sion: "E5", status: id === 1 ? "CORRECT" : "UNDERUTILIZED", reasons: [], entitlement_qty: "10000", debited_qty: "6000", allotted_qty: "500", billed_qty: "0", balance_qty: "3500", planned_qty: "1500", planned_cif: "900.00", max_unit_price: "0.60", licence_available_cif: "90000.00", licence_final_balance_cif: "50000.00", planning_eligible: id === 2, references: { boes: [], allotments: [] } })),
  } },
  recs: {},
} as Record<string, any>;

const fixturePath = process.env.LM_PIVOT_FIXTURE;
const data = fixturePath && fs.existsSync(fixturePath) ? JSON.parse(fs.readFileSync(fixturePath, "utf8")) : builtIn;
const NORM = process.env.LM_PIVOT_NORM || "E5";

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
    if (path === "item-pivot/available-norms/") return json(data.norms);
    if (path === "item-pivot/intelligence/") return json(data.intel[url.searchParams.get("sion_norm") ?? NORM] ?? data.intel[NORM]);
    if (path === "item-pivot/recommendations/") return json(Object.values(data.recs as Record<string, { data: unknown }>)[0]?.data ?? { read_only: true, errors: [], recommendations: [] });
    return json({ results: [], count: 0 });
  });
  return blocked;
}

const shot = (page: Page, path: string) => page.screenshot({ path, fullPage: true, animations: "disabled" });

test("item pivot intelligence — four views at 1440", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const blocked = await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/reports/item-pivot", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: new RegExp(`^${NORM}\\b`) }).first().click();
  await expect(page.getByRole("region", { name: "Utilization waterfall" })).toBeVisible();
  await shot(page, testInfo.outputPath("01-overview.png"));

  await page.getByRole("tab", { name: /Product Analysis/ }).click();
  await expect(page.getByRole("table", { name: "Products" })).toBeVisible();
  await shot(page, testInfo.outputPath("02-products.png"));

  const firstUsable = page.getByRole("table", { name: "Products" }).locator("tbody tr button[aria-pressed]").first();
  await firstUsable.click();
  await expect(page.getByRole("tab", { name: /Licence Analysis/ })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("list", { name: "Licences" }).getByRole("button", { name: /^Expand licence/ }).first().click();
  await expect(page.getByRole("region", { name: /products$/ }).first()).toBeVisible();
  await shot(page, testInfo.outputPath("03-licences.png"));

  await page.getByRole("tab", { name: "Planning & Optimization" }).click();
  await expect(page.getByRole("region", { name: "Additional planning capacity" })).toBeVisible();
  const boxes = page.getByRole("table", { name: "Planning candidates" }).getByRole("checkbox");
  if (await boxes.count()) {
    await boxes.first().check();
    await page.getByRole("button", { name: /Simulate recommendations/ }).click();
    await expect(page.getByRole("region", { name: "Recommendations" })).toBeVisible();
    await page.waitForLoadState("networkidle");
  }
  await shot(page, testInfo.outputPath("04-planning.png"));

  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBeFalsy();
  expect(errors).toEqual([]);
  expect(blocked).toEqual([]);
});
