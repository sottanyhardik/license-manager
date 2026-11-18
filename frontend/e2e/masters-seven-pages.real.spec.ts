import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND — acceptance for the eight master pages on the one generic licence-register template
 * (`GenericMasterCards` + `masterColumns.ts`): Companies, Ports, HS Codes, Head Norms, Groups, Item Names,
 * Exchange Rates, SION Classes (child norms shown in the expanded row).
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/masters-seven-pages.real.spec.ts`
 * (fresh `test_*` database, seeded, superuser). Every mutation uses an isolated record this spec creates.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";

interface PageCase {
    entity: string;
    title: string;
    /** Body for the isolated record created through the API. */
    create: Record<string, unknown>;
    /** Text shown as the row identifier (first column). */
    identifier: string;
    searchTerm: string;
    /** Form field changed through the real edit form, and its new value. */
    edit: { field: string; value: string };
    hasFilters: boolean;
    /** Extra body fields resolved at run time (e.g. an isolated parent record for a required FK). */
    prepare?: (page: Page) => Promise<Record<string, unknown>>;
    /** Child collection label shown when the row is expanded, and one child value in it. */
    nested?: { label: string; text: string };
}

const RUN = Date.now().toString().slice(-6);
const AUTH_STATE = "test-results/.masters-seven-auth.json";
// Unique per run (exchange-rate dates are unique), so a reused test DB does not refuse the isolated record.
const RATE_DATE = `2099-${String(1 + (Number(RUN) % 12)).padStart(2, "0")}-${String(1 + (Number(RUN) % 28)).padStart(2, "0")}`;
const CASES: PageCase[] = [
    { entity: "companies", title: "Companies", create: { iec: `25099${RUN.slice(-5)}`, name: `E2E Seven Co ${RUN}` }, identifier: `25099${RUN.slice(-5)}`, searchTerm: `E2E Seven Co ${RUN}`, edit: { field: "name", value: `E2E Seven Co ${RUN} renamed` }, hasFilters: true },
    { entity: "ports", title: "Ports", create: { code: `IN7${RUN.slice(-4)}`, name: `E2E Seven Port ${RUN}` }, identifier: `IN7${RUN.slice(-4)}`, searchTerm: `IN7${RUN.slice(-4)}`, edit: { field: "name", value: `E2E Seven Port ${RUN} renamed` }, hasFilters: false },
    { entity: "hs-codes", title: "HS Codes", create: { hs_code: `9${RUN}1`, product_description: `E2E seven HS ${RUN}` }, identifier: `9${RUN}1`, searchTerm: `9${RUN}1`, edit: { field: "product_description", value: `E2E seven HS ${RUN} renamed` }, hasFilters: true },
    { entity: "head-norms", title: "Head Norms", create: { name: `E2E Seven Head ${RUN}` }, identifier: `E2E Seven Head ${RUN}`, searchTerm: `E2E Seven Head ${RUN}`, edit: { field: "name", value: `E2E Seven Head ${RUN} renamed` }, hasFilters: false },
    { entity: "groups", title: "Groups", create: { name: `E2E Seven Group ${RUN}` }, identifier: `E2E Seven Group ${RUN}`, searchTerm: `E2E Seven Group ${RUN}`, edit: { field: "name", value: `E2E Seven Group ${RUN} renamed` }, hasFilters: false },
    { entity: "item-names", title: "Item Names", create: { name: `E2E SEVEN ITEM ${RUN}`, is_active: true }, identifier: `E2E SEVEN ITEM ${RUN}`, searchTerm: `E2E SEVEN ITEM ${RUN}`, edit: { field: "name", value: `E2E SEVEN ITEM ${RUN} RENAMED` }, hasFilters: true },
    {
        entity: "sion-classes", title: "SION Classes",
        create: { norm_class: `Z${RUN}`, description: `E2E SEVEN SION ${RUN}`, is_active: true, export_norm: [{ description: `E2E EXPORT ${RUN}`, quantity: "1.00", unit: "kg" }], import_norm: [] },
        identifier: `Z${RUN}`, searchTerm: `Z${RUN}`, edit: { field: "description", value: `E2E SEVEN SION ${RUN} RENAMED` }, hasFilters: true,
        prepare: async page => {
            const head = await api<{ id: number }>(page, "POST", "masters/head-norms/", { name: `E2E Sion Head ${RUN}` });
            expect(head.status, "isolated head norm created").toBe(201);
            return { head_norm: head.body!.id };
        },
        nested: { label: "Export items", text: `E2E EXPORT ${RUN}` },
    },
    { entity: "exchange-rates", title: "Exchange Rates", create: { date: RATE_DATE, usd: "84.1234", euro: "91.5678", pound_sterling: "107.0001", chinese_yuan: "11.6789" }, identifier: RATE_DATE, searchTerm: RATE_DATE, edit: { field: "usd", value: "84.4321" }, hasFilters: false },
];

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function api<T>(page: Page, method: "GET" | "POST", path: string, body?: unknown): Promise<{ status: number; body: T | null }> {
    return page.evaluate(async ([m, url, payload]) => {
        const access = localStorage.getItem("access");
        const response = await fetch(`/api/${url}`, {
            method: m as string,
            headers: { "Content-Type": "application/json", ...(access ? { Authorization: `Bearer ${access}` } : {}) },
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        return { status: response.status, body: response.ok ? await response.json() : null };
    }, [method, path, body] as const);
}

/** Vertical centres of the licence-register toolbar controls (null when absent). */
async function toolbar(page: Page) {
    return page.evaluate(() => {
        const mid = (el: Element | null | undefined) => (el ? Math.round(el.getBoundingClientRect().top + el.getBoundingClientRect().height / 2) : null);
        return {
            breadcrumb: mid(document.querySelector("nav[aria-label='Breadcrumb']")),
            h1: mid(document.querySelector("h1")),
            search: mid(document.querySelector("input[placeholder^='Search']")),
            filters: mid(Array.from(document.querySelectorAll("button")).find(b => b.textContent?.trim().startsWith("Filters"))),
            excel: mid(document.querySelector("[aria-label='Export to Excel']")),
            pdf: mid(document.querySelector("[aria-label='Export to PDF']")),
            addNew: mid(document.querySelector("[aria-label='Add New']")),
            filterPanelHidden: (document.querySelector("section[aria-label='Filters']") as HTMLElement | null)?.hidden ?? true,
        };
    });
}

test.describe("Eight master pages on the generic licence register template (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");
    test.describe.configure({ mode: "serial" });
    // One sign-in for the whole file (the login endpoint is rate limited); each test reuses the session.
    test.use({ viewport: { width: 1440, height: 900 }, storageState: AUTH_STATE });
    test.beforeAll(async ({ browser }) => {
        const context = await browser.newContext({ storageState: undefined });
        const page = await context.newPage();
        await signIn(page);
        await context.storageState({ path: AUTH_STATE });
        await context.close();
    });

    let licenceToolbarY = 0;

    test("licence reference toolbar", async ({ page }, testInfo) => {
        await page.goto("/licenses", { waitUntil: "networkidle" });
        licenceToolbarY = (await toolbar(page)).h1!;
        expect(licenceToolbarY).toBeGreaterThan(0);
        await page.screenshot({ path: testInfo.outputPath("seven-00-licences.png") });
    });

    for (const [index, c] of CASES.entries()) {
        test(`${c.title}: toolbar, search, record page, edit persisted`, async ({ page }, testInfo) => {
                await page.goto(`/masters/${c.entity}?page=1`, { waitUntil: "networkidle" });

            const extra = c.prepare ? await c.prepare(page) : {};
            const created = await api<Record<string, unknown>>(page, "POST", `masters/${c.entity}/`, { ...c.create, ...extra });
            expect(created.status, `${c.entity}: isolated record created`).toBe(201);
            // The identifier as the API returns it (dates come back in the app's DD-MM-YYYY format).
            const identifier = c.entity === "exchange-rates" ? String(created.body!.date) : c.identifier;

            // Toolbar: one licence-style row at the licence position; filters closed; Filters only where configured.
            await page.reload({ waitUntil: "networkidle" });
            await expect(page.getByRole("heading", { level: 1 })).toHaveText(c.title);
            const t = await toolbar(page);
            const ys = [t.breadcrumb, t.h1, t.search, t.filters, t.excel, t.pdf, t.addNew].filter((y): y is number => y !== null);
            expect(t.filters !== null, `${c.entity}: Filters control`).toBe(c.hasFilters);
            expect(ys).toHaveLength(c.hasFilters ? 7 : 6);
            expect(Math.max(...ys) - Math.min(...ys), `${c.entity}: one toolbar row`).toBeLessThanOrEqual(10);
            expect(Math.abs(t.h1! - licenceToolbarY), `${c.entity}: toolbar at the licence position`).toBeLessThanOrEqual(4);
            expect(t.filterPanelHidden, `${c.entity}: filters closed by default`).toBe(true);
            if (c.hasFilters) {
                await page.getByRole("button", { name: /^Filters/ }).click();
                await expect(page.locator("section[aria-label='Filters']")).toBeVisible();
                await page.getByRole("button", { name: /^Filters/ }).click();
            }

            // Search an actual record; compact licence-style row with the identifier as the record link.
            await page.getByPlaceholder(/Search by/).first().fill(c.searchTerm);
            const list = page.getByRole("list", { name: c.title });
            const row = list.getByRole("listitem").filter({ has: page.getByRole("link", { name: identifier, exact: true }) });
            await expect(row).toHaveCount(1);
            const rowBox = await row.locator("article").boundingBox();
            expect(rowBox!.height, `${c.entity}: compact row`).toBeLessThanOrEqual(56);
            await page.screenshot({ path: testInfo.outputPath(`seven-${String(index + 1).padStart(2, "0")}-${c.entity}.png`) });

            if (c.entity === "exchange-rates") {
                // Stored precision is shown as stored — never rounded for display.
                for (const field of ["usd", "euro", "pound_sterling", "chinese_yuan"] as const) {
                    await expect(row.getByText(String(created.body![field]), { exact: true }), `${field} shown as stored`).toBeVisible();
                }
            }

            if (c.nested) {
                await row.getByRole("button", { name: `Expand ${identifier}` }).click();
                await expect(row.getByRole("region", { name: c.nested.label }).getByText(c.nested.text, { exact: true })).toBeVisible();
            }

            // Record page.
            await row.getByRole("link", { name: identifier, exact: true }).click();
            await expect(page.getByRole("heading", { name: identifier, level: 1 })).toBeVisible();
            await expect(page.getByRole("link", { name: c.title, exact: true })).toHaveAttribute("href", `/masters/${c.entity}`);
            await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();

            // Edit through the real form; the change persists and shows on the list.
            await page.getByRole("link", { name: /Edit/ }).click();
            const input = page.locator(`#field-${c.edit.field}`);
            await expect(input).toBeVisible();
            await input.fill(c.edit.value);
            await page.getByRole("button", { name: "Update" }).click();
            await page.waitForURL(new RegExp(`/masters/${c.entity}$`));
            const id = created.body!.id;
            const saved = await api<Record<string, unknown>>(page, "GET", `masters/${c.entity}/${id}/`);
            expect(String(saved.body?.[c.edit.field]), `${c.entity}: edit persisted`).toBe(c.edit.value);
        });
    }

    test("Item Names: real pagination and a URL filter", async ({ page }) => {
        await page.goto("/masters/item-names?page=1", { waitUntil: "networkidle" });
        const all = await api<{ count: number }>(page, "GET", "masters/item-names/?page_size=1");
        expect(all.body!.count, "seeded item names span more than one page").toBeGreaterThan(25);
        await page.getByRole("navigation", { name: "Pagination" }).getByRole("button", { name: "Page 2", exact: true }).click();
        await expect(page).toHaveURL(/page=2/);
        await expect(page.getByRole("list", { name: "Item Names" }).getByRole("listitem")).toHaveCount(Math.min(25, all.body!.count - 25));

        const inactive = await api<{ count: number }>(page, "GET", "masters/item-names/?is_active=false&page_size=1");
        await page.goto("/masters/item-names?is_active=false&page=1", { waitUntil: "networkidle" });
        const rows = page.getByRole("list", { name: "Item Names" }).getByRole("listitem");
        if (inactive.body!.count === 0) {
            await expect(page.getByText(/^No item names found$/)).toBeVisible();
        } else {
            await expect(rows).toHaveCount(Math.min(25, inactive.body!.count));
            await expect(rows.getByText("Active", { exact: true })).toHaveCount(0);
        }
    });
});
