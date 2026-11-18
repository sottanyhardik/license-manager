import { expect, test, type Browser, type Page } from "@playwright/test";

/**
 * REAL BACKEND — the five modernized ERP workspaces: Licence list, Ledger Upload, Licence Ledger, Planning,
 * Incentive Licences. Shared toolbar (breadcrumb, title, closed Filters), real interactions, inline records,
 * and permission-denied behaviour for a viewer role.
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/workspaces.real.spec.ts` (fresh `test_*` database,
 * `seed_browser_2509`, superuser). Mutations use isolated records; the ledger upload is a CSV with no licence
 * rows (the parser creates nothing — backend/apps/license/api/views/ledger_upload.py).
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const AUTH_STATE = "test-results/.workspaces-auth.json";
const RUN = Date.now().toString().slice(-6);
const LICENCE_LIST = "/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=10%2C12%2C13%2C14%2C11%2C1%2C9";
const VIEWER = { username: `e2e_viewer_${RUN}`, password: `Vw!${RUN}xQ9pL2` };

async function signIn(page: Page, username = process.env.LM_USERNAME || "hardik", password = process.env.LM_PASSWORD || "admin@123") {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(username);
    await page.locator("#login-password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function api<T = Record<string, unknown>>(page: Page, method: string, path: string, body?: unknown): Promise<{ status: number; body: T }> {
    return page.evaluate(async ([m, url, payload]) => {
        const r = await fetch(`/api/${url}`, {
            method: m as string,
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access")}` },
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        return { status: r.status, body: await r.json().catch(() => ({})) };
    }, [method, path, body] as const) as Promise<{ status: number; body: T }>;
}

/** The shared Licence-register toolbar: breadcrumb + H1 on one row, Filters closed by default. */
async function expectWorkspaceToolbar(page: Page, title: string) {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(title);
    const geometry = await page.evaluate(() => {
        const mid = (el: Element | null) => (el ? Math.round(el.getBoundingClientRect().top + el.getBoundingClientRect().height / 2) : null);
        return { h1: mid(document.querySelector("h1")), crumb: mid(document.querySelector("nav[aria-label='Breadcrumb']")) };
    });
    expect(Math.abs(geometry.h1! - geometry.crumb!), `${title}: breadcrumb and title on one row`).toBeLessThanOrEqual(10);
    const panel = page.locator("section[aria-label='Filters']");
    if (await panel.count()) await expect(panel.first()).toBeHidden();
}

async function noOverflow(page: Page) {
    return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
}

test.describe("Five ERP workspaces (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");
    test.describe.configure({ mode: "serial" });
    test.use({ viewport: { width: 1440, height: 900 }, storageState: AUTH_STATE });
    test.beforeAll(async ({ browser }) => {
        const context = await browser.newContext({ storageState: undefined });
        const page = await context.newPage();
        await signIn(page);
        await context.storageState({ path: AUTH_STATE });
        await context.close();
    });

    test("Licence list: shared toolbar, filters, inline record with Edit tab", async ({ page }) => {
        await page.goto(LICENCE_LIST, { waitUntil: "networkidle" });
        await expectWorkspaceToolbar(page, "Licenses");
        await page.getByRole("button", { name: /^Filters/ }).click();
        await expect(page.locator("section[aria-label='Filters']")).toBeVisible();
        await page.getByRole("button", { name: /^Filters/ }).click();
        const first = page.getByRole("list", { name: "Licenses" }).getByRole("listitem").first();
        await first.getByRole("button", { name: /^Expand license / }).click();
        await expect(first.getByRole("tab", { name: "Edit" })).toBeVisible();
        expect(await noOverflow(page)).toBe(true);
    });

    test("Ledger Upload: toolbar, client-side rejection, real upload of a no-op CSV", async ({ page }) => {
        await page.goto("/ledger-upload", { waitUntil: "networkidle" });
        await expectWorkspaceToolbar(page, "Ledger Upload");
        const input = page.getByLabel("Ledger files");
        await input.setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not a ledger") });
        await expect(page.getByRole("alert").filter({ hasText: "File not accepted" })).toBeVisible();

        await input.setInputFiles({ name: `e2e-${RUN}.csv`, mimeType: "text/csv", buffer: Buffer.from("Header,Value\nnote,test\n") });
        const upload = page.waitForResponse(r => r.url().includes("upload-ledger") && r.request().method() === "POST");
        await page.getByRole("button", { name: "Upload & Process" }).click();
        const response = await upload;
        expect([200, 202]).toContain(response.status());
        await expect(page.getByRole("alert").filter({ hasText: "Upload problem" })).toHaveCount(0);
        expect(await noOverflow(page)).toBe(true);
    });

    test("Licence Ledger: toolbar, collapsed filters, search, actions menu, Excel export", async ({ page }) => {
        await page.goto("/license-ledger", { waitUntil: "networkidle" });
        await expectWorkspaceToolbar(page, "License Ledger");
        await page.getByRole("button", { name: /^Filters/ }).click();
        await expect(page.locator("section[aria-label='Filters']")).toBeVisible();
        await page.getByRole("button", { name: /^Filters/ }).click();

        await page.getByRole("button", { name: "More ledger actions" }).click();
        await expect(page.getByRole("menuitem", { name: "License Downloads" })).toBeVisible();
        await expect(page.getByRole("menuitem", { name: "Choose Folder & Start" })).toBeVisible();
        await page.keyboard.press("Escape");

        await page.getByPlaceholder("License # or exporter...").fill("3411008090");
        await expect(page.getByText("3411008090").first()).toBeVisible();
        const [download] = await Promise.all([
            page.waitForEvent("download", { timeout: 60_000 }),
            page.getByRole("button", { name: "Download license ledger as Excel" }).click(),
        ]);
        expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
        expect(await noOverflow(page)).toBe(true);
    });

    test("Planning: toolbar and consolidated actions menu", async ({ page }) => {
        await page.goto("/planning", { waitUntil: "networkidle" });
        await expectWorkspaceToolbar(page, "Planning");
        await page.getByRole("button", { name: "More planning actions" }).click();
        await expect(page.getByRole("menuitem", { name: "Plan all expired licences" })).toBeVisible();
        await expect(page.getByRole("menuitem", { name: "Re-plan all eligible licences" })).toBeVisible();
        await page.keyboard.press("Escape");
        expect(await noOverflow(page)).toBe(true);
    });

    test("Incentive Licences: toolbar, compact rows, inline record, edit/cancel/save, old /edit URL", async ({ page }) => {
        await page.goto("/incentive-licenses?page=1", { waitUntil: "networkidle" });
        const company = (await api<{ results: { id: number }[] }>(page, "GET", "masters/companies/?page_size=1")).body.results[0];
        const port = (await api<{ results: { id: number }[] }>(page, "GET", "masters/ports/?page_size=1")).body.results[0];
        const number = `E2EINC${RUN}`;
        const created = await api(page, "POST", "incentive-licenses/", {
            license_type: "RODTEP", license_number: number, license_date: "2026-04-01", license_expiry_date: "2099-03-31",
            exporter: company.id, port_code: port.id, license_value: "100000.00", is_active: true, notes: "e2e",
        });
        expect(created.status, JSON.stringify(created.body).slice(0, 300)).toBe(201);
        const id = created.body.id as number;

        await page.goto(`/incentive-licenses?search=${number}&page=1`, { waitUntil: "networkidle" });
        await expectWorkspaceToolbar(page, "Incentive Licenses");
        const list = page.getByRole("list", { name: "Incentive Licenses" });
        const row = list.getByRole("listitem").filter({ has: page.getByRole("link", { name: number, exact: true }) });
        await expect(row).toHaveCount(1);
        await expect(row.getByText("₹1,00,000").first()).toBeVisible();
        await list.evaluate(el => { (el as HTMLElement & { __kept?: boolean }).__kept = true; });

        await row.getByRole("link", { name: number, exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/incentive-licenses/${id}(\\\\?|$)`));
        const region = page.getByRole("region", { name: `${number} details` });
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

        await region.getByRole("tab", { name: "Edit" }).click();
        await expect(region.locator("#field-notes")).toBeVisible();
        await region.locator("#field-notes").fill("discarded");
        await region.getByRole("button", { name: "Cancel" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
        expect((await api<{ notes: string }>(page, "GET", `incentive-licenses/${id}/`)).body.notes).toBe("e2e");

        await region.getByRole("tab", { name: "Edit" }).click();
        await region.locator("#field-notes").fill(`saved ${RUN}`);
        await region.getByRole("button", { name: "Update" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
        await expect.poll(async () => (await api<{ notes: string }>(page, "GET", `incentive-licenses/${id}/`)).body.notes).toBe(`saved ${RUN}`);
        expect(await list.evaluate(el => (el as HTMLElement & { __kept?: boolean }).__kept === true), "saved without navigation").toBe(true);

        await page.goto(`/incentive-licenses/${id}/edit`, { waitUntil: "networkidle" });
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("Incentive Licenses");
        await expect(page.getByRole("region", { name: `${number} details` }).getByRole("tab", { name: "Edit", selected: true })).toBeVisible();
        expect(await noOverflow(page)).toBe(true);
    });

    test("permissions: a viewer sees no write actions, is refused by the API, and is kept out of manager-only workspaces", async ({ page, browser }) => {
        await page.goto("/dashboard", { waitUntil: "networkidle" });
        const made = await api(page, "POST", "auth/users/", {
            username: VIEWER.username, password: VIEWER.password, email: `${VIEWER.username}@example.invalid`,
            is_active: true, roles: ["LICENSE_VIEWER", "INCENTIVE_LICENSE_VIEWER"],
        });
        expect(made.status, JSON.stringify(made.body).slice(0, 300)).toBe(201);
        const incentive = (await api<{ results: { id: number; license_number: string }[] }>(page, "GET", "incentive-licenses/?page_size=1")).body.results[0];

        const viewer = await viewerPage(browser);
        try {
            // Incentive: record opens read-only (no Edit tab, no Edit/Delete actions); the API refuses writes.
            await viewer.goto(`/incentive-licenses/${incentive.id}`, { waitUntil: "networkidle" });
            const region = viewer.getByRole("region", { name: `${incentive.license_number} details` });
            await expect(region.getByRole("tab", { name: "Overview" })).toBeVisible();
            await expect(region.getByRole("tab", { name: "Edit" })).toHaveCount(0);
            await viewer.getByRole("button", { name: `Actions for ${incentive.license_number}` }).click();
            await expect(viewer.getByRole("menuitem", { name: "Edit" })).toHaveCount(0);
            await expect(viewer.getByRole("menuitem", { name: /Delete/ })).toHaveCount(0);
            await viewer.keyboard.press("Escape");
            expect((await api(viewer, "PATCH", `incentive-licenses/${incentive.id}/`, { notes: "viewer" })).status).toBe(403);
            await expect(viewer.getByRole("link", { name: "Add New" })).toHaveCount(0);

            // Old edit URL for a viewer: list + record, never an Edit tab.
            await viewer.goto(`/incentive-licenses/${incentive.id}/edit`, { waitUntil: "networkidle" });
            await expect(viewer.getByRole("region", { name: `${incentive.license_number} details` }).getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
            await expect(viewer.getByRole("tab", { name: "Edit" })).toHaveCount(0);

            // Licence: viewer has no Edit tab; the API refuses a licence write.
            await viewer.goto(LICENCE_LIST, { waitUntil: "networkidle" });
            const lic = viewer.getByRole("list", { name: "Licenses" }).getByRole("listitem").first();
            await lic.getByRole("button", { name: /^Expand license / }).click();
            await expect(lic.getByRole("tab", { name: "Overview" })).toBeVisible();
            await expect(lic.getByRole("tab", { name: "Edit" })).toHaveCount(0);
            expect((await api(viewer, "PATCH", "licenses/2509/", { file_number: "viewer" })).status).toBe(403);

            // Manager-only workspaces are refused (route guard) — the API stays authoritative.
            for (const path of ["/planning", "/ledger-upload"]) {
                await viewer.goto(path, { waitUntil: "networkidle" });
                await expect(viewer, `${path} refused for a viewer`).toHaveURL(/\/403$/);
            }
        } finally {
            await viewer.context().close();
        }
    });
});

async function viewerPage(browser: Browser): Promise<Page> {
    const context = await browser.newContext({ storageState: undefined, viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await signIn(page, VIEWER.username, VIEWER.password);
    return page;
}
