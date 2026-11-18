import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

/**
 * Mocked-API visual check of /planning (SION norm accordion + inline tabs).
 *
 * Default data is test-only and mirrors the shape of the read-only
 * `norm-summary` / `norm-configuration` endpoints. To screenshot real local
 * configuration, dump those responses to JSON ({summary, config: {id: …},
 * rules: {id: […]}}) and set LM_PLANNING_FIXTURE=/path/to/fixture.json.
 * Every non-GET /api request is aborted and asserted absent.
 */
const user = { id: 1, username: "visual.operator", first_name: "Visual", last_name: "Operator", is_superuser: false, roles: ["LICENSE_MANAGER"] };

type Fixture = { summary: Record<string, unknown>[]; config: Record<string, unknown>; rules: Record<string, unknown[]> };

const base = { is_active: true, active_rule_count: 0, split_rule_count: 0, rule_version_count: 0, max_rule_version: null, last_updated: null, profile_version: null, profile_action_count: 0, registry_rule_count: 0, registry_action_count: 0, registry_split_count: 0, has_entitlement_profile: false };
const builtIn: Fixture = {
  summary: [
    { ...base, id: 1, norm_class: "E1", description: "Assorted Confectionery (with Sugar)", active_rule_count: 2, rule_version_count: 3, max_rule_version: 2, last_updated: "2026-08-20T15:39:20Z" },
    { ...base, id: 5, norm_class: "E126", description: "Vegetable Pickles in Oil / Mixed Pickles in Oil", is_active: false, registry_rule_count: 4, registry_action_count: 7, registry_split_count: 1, has_entitlement_profile: true },
    { ...base, id: 11, norm_class: "E132", description: "Namkeens / Mixtures / Savouries", registry_rule_count: 2, registry_action_count: 2, registry_split_count: 1 },
    { ...base, id: 2, norm_class: "E5", description: "Biscuits", active_rule_count: 1, split_rule_count: 1, rule_version_count: 1, max_rule_version: 1, profile_version: 1, profile_action_count: 3 },
    { ...base, id: 19, norm_class: "PP", description: "PP" },
  ],
  config: {},
  rules: {
    1: [
      { id: 10, sion: 1, stable_key: "E1:RULE:001:SUGAR", name: "Sugar", expression: { operator: "AND", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1701" }] }, max_unit_price: "0.60", unit: "KG", priority: 1, is_active: true, strategy: "STANDARD", import_item: 1, standard_item_name: "SUGAR - E1", unit_value_rows: [], percentage_rows: [], version: 2, modified_on: "2026-08-20T15:39:20Z", modified_by_username: "visual.operator" },
      { id: 11, sion: 1, stable_key: "E1:RULE:002:MILK", name: "Milk powder", expression: { operator: "OR", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "0402" }, { field: "PRODUCT_DESCRIPTION", comparator: "CONTAINS", value: "milk" }] }, max_unit_price: "3.50", unit: "KG", priority: 2, is_active: true, strategy: "STANDARD", import_item: 2, standard_item_name: "MILK POWDER - E1", unit_value_rows: [], percentage_rows: [], version: 1, modified_on: "2026-08-19T10:00:00Z" },
    ],
    2: [{ id: 20, sion: 2, stable_key: "E5:RULE:001:FAT", name: "Edible fat split", expression: { operator: "AND", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1511" }] }, max_unit_price: "1.80", unit: "KG", priority: 1, is_active: true, strategy: "SPLIT_BY_PERCENT", import_item: null, unit_value_rows: [], percentage_rows: [{ import_item: 7, percentage: "60.00", unit_price: "1.20" }, { import_item: 8, percentage: "40.00", unit_price: "1.80" }], version: 1 }],
  },
};
const e126Registry = {
  source: "sion_legacy_configurations.LEGACY_PLANNER_CONFIGURATIONS",
  rules: [
    { stable_key: "E126:RULE:001:NUTS", name: "Nuts", priority: 1, expression: { operator: "OR", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "0802" }] }, max_unit_price: "3.00", unit: "KG", output_key: "NUTS" },
    { stable_key: "E126:RULE:002:PKO_OLIVE_SPLIT", name: "Palm Kernel / Olive Oil split", priority: 2, expression: { operator: "AND", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1513" }, { field: "HSN", comparator: "STARTS_WITH", value: "1509" }] }, max_unit_price: "5.00", unit: "KG", output_key: "PKO_OLIVE_SPLIT" },
    { stable_key: "E126:RULE:003:PKO", name: "Palm Kernel Oil", priority: 3, expression: { operator: "OR", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1513" }] }, max_unit_price: "1.80", unit: "KG", output_key: "PKO" },
    { stable_key: "E126:RULE:004:OLIVE", name: "Olive Oil", priority: 4, expression: { operator: "OR", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "1509" }] }, max_unit_price: "5.00", unit: "KG", output_key: "OLIVE" },
  ],
  actions: [
    { stable_key: "E126:ACTION:002:SPLIT", priority: 2, action_type: "SPLIT", config: { source_output: "PKO_OLIVE_SPLIT", basis: "RECORD_AVAILABLE_QUANTITY", targets: { PKO: "0.5", OLIVE: "0.5" } } },
    { stable_key: "E126:ACTION:005:REBALANCE", priority: 5, action_type: "REBALANCE", config: { mode: "VALUE_GAIN_SHIFT", source: "PKO", target: "OLIVE", eligible_source: "PKO_OLIVE_SPLIT", stop_at_balance: true } },
  ],
  mappings: [
    { stable_key: "E126:OUTPUT:002:PKO", priority: 2, source_key: "PKO", output_name: "PALM KERNEL OIL - E126", rate: "1.80", conversion_factor: "1", unit: "KG" },
    { stable_key: "E126:OUTPUT:003:OLIVE", priority: 3, source_key: "OLIVE", output_name: "OLIVE OIL - E126", rate: "5.00", conversion_factor: "1", unit: "KG" },
  ],
};
builtIn.config = {
  5: {
    sion: { id: 5, norm_class: "E126", description: "Vegetable Pickles in Oil / Mixed Pickles in Oil", is_active: false }, rule_versions: [], profiles: [], audit: [],
    registry: e126Registry,
    entitlement_profile: {
      source: "sion_planner_config.entitlement_profiles",
      groups: [{ key: "VEGETABLE_OIL", label: "Vegetable Oil", entitlement_items: ["PALM KERNEL OIL", "OLIVE OIL"], source_rule: "E126:RULE:002:PKO_OLIVE_SPLIT", split_action: "E126:ACTION:002:SPLIT", products: [{ name: "Sunflower Oil", entitlement: "OLIVE OIL", aliases: ["SUNFLOWER"] }, { name: "Olive Oil", entitlement: "OLIVE OIL", aliases: ["OLIVE"] }, { name: "PKO", entitlement: "PALM KERNEL OIL", aliases: ["PALM KERNEL", "PKO"] }] }],
      entitlements: [{ item: "PALM KERNEL OIL", label: "PKO", split_target: "PKO", valuation: "RATE", sequence: 1 }, { item: "OLIVE OIL", label: "Olive Oil + Sunflower Oil", split_target: "OLIVE", valuation: "RESIDUAL", sequence: 2 }],
    },
  },
};

const fixturePath = process.env.LM_PLANNING_FIXTURE;
const data: Fixture = fixturePath && fs.existsSync(fixturePath) ? JSON.parse(fs.readFileSync(fixturePath, "utf8")) : builtIn;
const emptyConfig = (id: number) => {
  const row = data.summary.find((s) => s.id === id) ?? {};
  return { sion: { id, norm_class: row.norm_class, description: row.description, is_active: row.is_active }, rule_versions: [], profiles: [], registry: null, entitlement_profile: null, audit: [] };
};

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
    if (url.pathname.endsWith("/auth/me/")) return json(user);
    if (url.pathname.endsWith("/sion-planning-rules/norm-summary/")) return json(data.summary);
    if (url.pathname.endsWith("/sion-planning-rules/norm-configuration/")) {
      const id = Number(url.searchParams.get("sion"));
      return json(data.config[id] ?? emptyConfig(id));
    }
    if (url.pathname.endsWith("/sion-planning-rules/")) return json(data.rules[Number(url.searchParams.get("sion"))] ?? []);
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

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);

test.describe("planning workspace visual", () => {
  test("collapsed list, E126 overview / rules / split / validation at 1440", async ({ page }, testInfo) => {
    const errors = watchConsole(page);
    const blocked = await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.goto("/planning", { waitUntil: "networkidle" });
    await expect(page.getByRole("article", { name: "SION norm E126" })).toBeVisible();
    await expect(page.getByRole("region", { name: /workspace$/ })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("01-planning-collapsed.png"), fullPage: true, animations: "disabled" });

    await page.getByRole("button", { name: "Expand SION norm E126" }).click();
    const region = page.getByRole("region", { name: "SION norm E126 workspace" });
    await expect(region.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/sion=E126/);
    await page.screenshot({ path: testInfo.outputPath("02-e126-overview.png"), fullPage: true, animations: "disabled" });

    await region.getByRole("tab", { name: /^Rules/ }).click();
    await expect(region.getByRole("region", { name: "Code registry rules" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("03-e126-rules.png"), fullPage: true, animations: "disabled" });

    await region.getByRole("tab", { name: "Split Configuration" }).click();
    const split = region.getByRole("table", { name: "Split entitlements" });
    await expect(split.getByText("50%")).toHaveCount(2);
    await expect(split.getByText("Sunflower Oil → Olive Oil + Sunflower Oil")).toBeVisible();
    await expect(split.getByText("PKO → PKO")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath("04-e126-split.png"), fullPage: true, animations: "disabled" });

    await region.getByRole("tab", { name: /^Validation/ }).click();
    await expect(region.getByRole("region", { name: "Configuration validation" })).toBeVisible();
    await expect(region.getByRole("tab", { name: /^Validation/ })).toHaveAttribute("data-state", "active");
    await expect(region.getByRole("tab", { name: "Split Configuration" })).toHaveAttribute("data-state", "inactive");
    await page.screenshot({ path: testInfo.outputPath("05-e126-validation.png"), fullPage: true, animations: "disabled" });

    // Refresh keeps the norm and the tab; Back collapses the row.
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByRole("region", { name: "SION norm E126 workspace" }).getByRole("tab", { name: /^Validation/ })).toHaveAttribute("aria-selected", "true");
    await page.goBack();
    await expect(page).toHaveURL(/\/planning$/);
    await expect(page.getByRole("region", { name: "SION norm E126 workspace" })).toHaveCount(0);
    await page.goForward();
    await expect(page.getByRole("region", { name: "SION norm E126 workspace" })).toBeVisible();

    expect(await noOverflow(page)).toBeFalsy();
    expect(errors).toEqual([]);
    expect(blocked).toEqual([]);
  });

  for (const norm of ["E1", "E132", "E5", "PP"]) {
    test(`${norm} expands inline with its configured tabs`, async ({ page }, testInfo) => {
      const errors = watchConsole(page);
      const blocked = await mockApi(page);
      await page.setViewportSize({ width: 1440, height: 960 });
      await page.goto("/planning", { waitUntil: "networkidle" });
      await page.getByRole("button", { name: `Expand SION norm ${norm}`, exact: true }).click();
      const region = page.getByRole("region", { name: `SION norm ${norm} workspace` });
      await expect(region.getByRole("tab", { name: "Overview" })).toBeVisible();
      const tabs = await region.getByRole("tab").all();
      for (const [index, tab] of tabs.entries()) {
        await tab.click();
        await expect(tab).toHaveAttribute("aria-selected", "true");
        await page.screenshot({ path: testInfo.outputPath(`norm-${norm}-${index + 1}.png`), fullPage: true, animations: "disabled" });
      }
      await page.screenshot({ path: testInfo.outputPath(`norm-${norm}.png`), fullPage: true, animations: "disabled" });
      expect(errors).toEqual([]);
      expect(blocked).toEqual([]);
    });
  }

  for (const size of [{ name: "768", width: 768, height: 1024 }, { name: "390", width: 390, height: 844 }]) {
    test(`responsive ${size.name}`, async ({ page }, testInfo) => {
      const errors = watchConsole(page);
      await mockApi(page);
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto("/planning?sion=E126&view=split", { waitUntil: "networkidle" });
      await expect(page.getByRole("table", { name: "Split entitlements" })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`planning-${size.name}.png`), fullPage: true, animations: "disabled" });
      expect(await noOverflow(page)).toBeFalsy();
      expect(errors).toEqual([]);
    });
  }
});
