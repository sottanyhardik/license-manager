import { expect, test, type Page } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

/**
 * BOE register → record workspace workflow (local mock, no backend).
 * Verifies the BOE module uses the same compact register and workspace
 * patterns as Licence, role gating, the inline invoice edit request, and
 * responsive containment. Requests are recorded so the tests can assert that
 * each workspace tab only calls its own endpoint.
 */
type Role = "BOE_MANAGER" | "BOE_VIEWER";

const userFor = (roles: string[]) => ({
  id: 1, username: "boe.operator", first_name: "Boe", last_name: "Operator", is_superuser: false, roles,
});

const BOES = [
  {
    id: 201, bill_of_entry_number: "7012345", bill_of_entry_date: "05-01-2025", port_name: "INNSA1", company_name: "Alpha Imports",
    product_name: "Crude Palm Oil", invoice_no: "INV-201", invoice_date: "06-01-2025", licenses: "0310123456",
    total_inr: "1234567.89", total_fc: "15000.5", total_quantity: "12.3456", unit_price: "1215.03",
    exchange_rate: "82.30", appraisement: "Yes", ooc_date: "07-01-2025", cha: "Beta CHA", comments: null,
    allotment: [301], boe_pdf_copy: null,
    item_details: [
      { id: 1, license_id: 11, license_number: "0310123456", item_description: "Palm oil", hs_code: "15119000", qty: "12.3456", cif_fc: "15000.5", cif_inr: "1234567.89", is_dispute: false, item_serial_number: 3 },
    ],
  },
  {
    id: 202, bill_of_entry_number: "7012346", bill_of_entry_date: "15-08-2025", port_name: "INMAA1", company_name: null,
    product_name: "", invoice_no: "", licenses: "0310654321",
    total_inr: "8200", total_fc: "100", total_quantity: "2", unit_price: null, allotment: [], boe_pdf_copy: null,
    item_details: [
      { id: 2, license_id: 12, license_number: "0310654321", item_description: "Cashew", hs_code: "08013100", qty: "2", cif_fc: "100", cif_inr: "8200", is_dispute: true },
    ],
  },
];

const listEnvelope = (results: unknown[]) => ({
  results, count: results.length, list_display: [], form_fields: [], search_fields: [], filter_fields: [],
  filter_config: {}, ordering_fields: [], nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {},
  inline_editable: ["invoice_no"], current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false,
});

async function mockApi(page: Page, roles: string[]) {
  const user = userFor(roles);
  const requests: string[] = [];
  await page.addInitScript((u) => {
    localStorage.setItem("access", "boe-test-access-token");
    localStorage.setItem("refresh", "boe-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const req = route.request();
    const { pathname } = new URL(req.url());
    requests.push(`${req.method()} ${pathname}`);
    const json = (body: unknown) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    if (pathname.endsWith("/auth/me/")) return json(user);
    if (/\/bill-of-entries\/\d+\/update-invoice-no\/$/.test(pathname)) return json({ success: true });
    const detail = pathname.match(/\/bill-of-entries\/(\d+)\/$/);
    if (detail) return json(BOES.find((b) => String(b.id) === detail[1]) ?? {});
    if (pathname.endsWith("/bill-of-entries/")) return json(listEnvelope(BOES));
    if (/\/allotments\/301\/$/.test(pathname)) {
      return json({ id: 301, company_name: "Alpha Imports", item_name: "Palm oil", required_quantity: "12", cif_inr: "1000", cif_fc: "12", allotment_details: [] });
    }
    if (pathname.endsWith("/licenses/")) return json(listEnvelope([]));
    return json({ results: [], count: 0 });
  });
  return requests;
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

const card = (page: Page, number: string) =>
  page.locator("article, [data-entity-card], .entity-card, div").filter({ has: page.getByRole("link", { name: number, exact: true }) }).last();

test.describe("BOE register (compact ERP register, Licence parity)", () => {
  test("manager sees the compact toolbar, Add New target and secondary actions menu", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mockApi(page, ["BOE_MANAGER"] satisfies Role[]);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/bill-of-entries", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { level: 1, name: "Bills of Entry" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Bills of Entry");
    await expect(page.getByText("2 records")).toBeVisible();

    const addNew = page.getByRole("link", { name: /add new/i });
    await expect(addNew).toHaveAttribute("href", "/bill-of-entries/create");

    await page.getByRole("button", { name: "More bill of entry actions" }).click();
    await expect(page.getByRole("menuitem", { name: "Port-wise Excel" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Update all empty product names" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);
    // Radix removes the aria-hidden it applies to siblings once the menu has fully closed.
    await expect(page.locator(".app-shell__content [aria-hidden=true]:has(a, button)")).toHaveCount(0);

    await expectNoBasicSemanticViolations(page);
    await expectNoSeriousOrCriticalAxeViolations(page, "main");
    expect(errors).toEqual([]);
  });

  test("BOE and Licence registers share the same toolbar geometry", async ({ page }) => {
    await mockApi(page, ["BOE_MANAGER", "LICENSE_MANAGER"]);
    await page.setViewportSize({ width: 1440, height: 900 });
    const measure = async (path: string) => {
      await page.goto(path, { waitUntil: "networkidle" });
      const h1 = page.getByRole("heading", { level: 1 });
      await expect(h1).toHaveCount(1);
      // The h1 follows the breadcrumb inline, so compare the toolbar start edge (breadcrumb) plus h1 baseline/type.
      const crumb = await page.getByRole("navigation", { name: "Breadcrumb" }).boundingBox();
      const box = await h1.boundingBox();
      const font = await h1.evaluate((el) => getComputedStyle(el).fontSize);
      return { top: Math.round(box!.y), left: Math.round(crumb!.x), font };
    };
    const licence = await measure("/licenses");
    const boe = await measure("/bill-of-entries");
    expect(boe.font).toBe(licence.font);
    expect(Math.abs(boe.top - licence.top)).toBeLessThanOrEqual(4);
    expect(Math.abs(boe.left - licence.left)).toBeLessThanOrEqual(4);
  });

  test("viewer gets read-only register and cards", async ({ page }) => {
    await mockApi(page, ["BOE_VIEWER"] satisfies Role[]);
    await page.goto("/bill-of-entries", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { level: 1, name: "Bills of Entry" })).toBeVisible();
    await expect(page.getByRole("link", { name: /add new/i })).toHaveCount(0);
    // D2: viewers may edit the invoice number inline; they get no menu actions
    // (no Transfer Letter - owner decision - and no write actions).
    await expect(card(page, "7012345").locator('button[title="Click to edit invoice number"]')).toBeVisible();
    await card(page, "7012345").locator('button[title="View details"]').first().click();
    await expect(page.getByRole("button", { name: "Actions for BOE 7012345" })).toHaveCount(0);
    await expect(page.getByRole("menuitem", { name: "Transfer Letter" })).toHaveCount(0);
  });
});

test.describe("BOE record workspace", () => {
  test("card expands into the shared workspace; each tab calls only its own endpoint", async ({ page }) => {
    const requests = await mockApi(page, ["BOE_MANAGER"]);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/bill-of-entries", { waitUntil: "networkidle" });

    await card(page, "7012345").locator('button[title="View details"]').first().click();
    const tabs = page.getByRole("tablist", { name: "BOE 7012345 sections" });
    await expect(tabs).toBeVisible();
    await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toContainText("₹12,34,567.89");
    await expect(page.getByRole("tab", { name: "Edit Options" })).toHaveCount(0);

    const before = requests.length;
    await page.getByRole("tab", { name: "Import Items" }).click();
    await expect(page.getByRole("region", { name: "BOE 7012345 details" })).toContainText("Palm oil");
    expect(requests.slice(before)).toEqual([]);

    await page.getByRole("tab", { name: "BOE Details" }).click();
    await expect(page.getByRole("tabpanel")).toContainText("Beta CHA");
    expect(requests.filter((r) => r === "GET /api/bill-of-entries/201/")).toHaveLength(1);

    await page.getByRole("tab", { name: "Allotment Mapping" }).click();
    await expect(page.getByRole("tabpanel")).toContainText("Alpha Imports");
    expect(requests.filter((r) => r === "GET /api/allotments/301/")).toHaveLength(1);

    await page.getByRole("tab", { name: "Documents" }).click();
    await expect(page.getByRole("region", { name: "Licence copies" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open License Copy PDF for 0310123456" })).toBeVisible();
    expect(requests.filter((r) => r.includes("merged-documents"))).toEqual([]);
  });

  test("inline invoice edit saves on Enter and cancels on Escape", async ({ page }) => {
    const requests = await mockApi(page, ["BOE_MANAGER"]);
    await page.goto("/bill-of-entries", { waitUntil: "networkidle" });

    await page.getByRole("button", { name: /Add Invoice No/ }).click();
    const input = page.getByRole("textbox", { name: "Invoice number" });
    await expect(input).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(input).toHaveCount(0);

    await page.getByRole("button", { name: /Add Invoice No/ }).click();
    await page.getByRole("textbox", { name: "Invoice number" }).fill("INV-202");
    await page.keyboard.press("Enter");
    await expect.poll(() => requests.filter((r) => r === "POST /api/bill-of-entries/202/update-invoice-no/").length).toBe(1);
  });
});

test.describe("BOE responsive containment", () => {
  for (const vp of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
    test(`register and workspace fit ${vp.width}px`, async ({ page }, testInfo) => {
      await mockApi(page, ["BOE_MANAGER"]);
      await page.setViewportSize(vp);
      await page.goto("/bill-of-entries", { waitUntil: "networkidle" });
      await expect(page.getByRole("heading", { level: 1, name: "Bills of Entry" })).toBeVisible();
      await expectNoDocumentOverflow(page);
      // Icon-only toolbar actions below `sm` must keep accessible names.
      await expectNoSeriousOrCriticalAxeViolations(page, "main");
      await card(page, "7012345").locator('button[title="View details"]').first().click();
      await expect(page.getByRole("tablist", { name: "BOE 7012345 sections" })).toBeVisible();
      await expectNoDocumentOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`boe-${vp.width}.png`), fullPage: true });
    });
  }
});
