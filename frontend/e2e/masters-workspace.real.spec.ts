import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND WORKFLOW — Masters workspace (generic master framework).
 *
 * Opt-in: run through `scripts/test/run_data_bearing_browser_e2e.sh e2e/masters-workspace.real.spec.ts`,
 * which creates a fresh `test_*` database, seeds it (`seed_browser_2509`, superuser
 * login) and sets LM_REAL_E2E=1. Never point it at a shared database.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const CODE = "E2E/9901"; // slash-coded like real notifications (025/2023)
const PORT_CODE = "INE2E1";

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

/** Search the list and wait until the debounced request has narrowed it to CODE only. */
async function searchUntilOnly(page: Page, term: string) {
    await page.getByPlaceholder(/Search by/).first().fill(term);
    await expect(page.getByRole("link", { name: CODE, exact: true })).toBeVisible();
    await expect(page.getByRole("list", { name: "Notification Numbers" }).getByRole("listitem")).toHaveCount(1);
}

async function rowAction(page: Page, action: "Open" | "Edit" | "Delete") {
    await page.getByRole("button", { name: `Actions for ${CODE}` }).click();
    await page.getByRole("menuitem", { name: action }).click();
}

async function authPost<T>(page: Page, path: string, body: unknown): Promise<{ status: number; body: T | null }> {
    return page.evaluate(async ([url, payload]) => {
        const access = localStorage.getItem("access");
        const response = await fetch(`/api/${url}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...(access ? { Authorization: `Bearer ${access}` } : {}) },
            body: JSON.stringify(payload),
        });
        return { status: response.status, body: response.ok ? await response.json() : null };
    }, [path, body] as const);
}

async function authGet<T>(page: Page, path: string): Promise<{ status: number; body: T | null }> {
    return page.evaluate(async (url) => {
        const access = localStorage.getItem("access");
        const response = await fetch(`/api/${url}`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
        return { status: response.status, body: response.ok ? await response.json() : null };
    }, path);
}

test.describe("Masters workspace on the real backend", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");
    test.describe.configure({ mode: "serial" });

    test("hub lists every category and opens a master", async ({ page }) => {
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        await signIn(page);
        await page.goto("/masters", { waitUntil: "networkidle" });
        await expect(page.getByRole("heading", { name: "Masters", level: 1 })).toBeVisible();
        for (const category of ["Parties & places", "Items & SION norms", "Licence & customs reference", "Rates & pricing"]) {
            await expect(page.getByRole("heading", { name: category })).toBeVisible();
        }
        // Counts come from the real API; the seeded scenario has at least one company.
        await expect(page.getByTestId("master-count-companies")).not.toHaveText("—");
        await expect(page.getByTestId("master-count-companies")).toHaveText(/^[1-9][\d,]*$/);

        await page.getByRole("searchbox", { name: "Search masters" }).fill("notification");
        await expect(page.getByRole("link", { name: /Companies/ })).toHaveCount(0);
        await page.getByRole("link", { name: /Notification Numbers/ }).click();
        await page.waitForURL("**/masters/notification-numbers");
        expect(errors).toEqual([]);
    });

    test("create, search, edit and delete a slash-coded notification number", async ({ page }) => {
        await signIn(page);
        await page.goto("/masters/notification-numbers/create", { waitUntil: "networkidle" });
        await page.locator("#field-code").fill(CODE);
        await page.locator("#field-label").fill("E2E notification");
        await page.getByRole("button", { name: "Create" }).click();
        await page.waitForURL(/\/masters\/notification-numbers$/);

        const created = await authGet<{ code: string; label: string }>(page, `masters/notification-numbers/${encodeURIComponent(CODE)}/`);
        expect(created.status).toBe(200);
        expect(created.body?.label).toBe("E2E notification");

        await searchUntilOnly(page, "E2E/99");

        await rowAction(page, "Edit");
        await page.waitForURL(`**/masters/notification-numbers/${encodeURIComponent(CODE)}/edit`);
        await expect(page.locator("#field-label")).toHaveValue("E2E notification");
        await page.locator("#field-label").fill("E2E notification renamed");
        await page.getByRole("button", { name: "Update" }).click();
        await page.waitForURL(/\/masters\/notification-numbers$/);
        const edited = await authGet<{ label: string }>(page, `masters/notification-numbers/${encodeURIComponent(CODE)}/`);
        expect(edited.body?.label).toBe("E2E notification renamed");
        // The list we return to must show the saved value, not a cached page.
        await expect(page.getByText("E2E notification renamed", { exact: true })).toBeVisible();

        // Record page: real fields + the real audit entry the server logged for the PATCH.
        await searchUntilOnly(page, "E2E/99");
        await page.getByRole("link", { name: CODE, exact: true }).click();
        await page.waitForURL(`**/masters/notification-numbers/${encodeURIComponent(CODE)}`);
        await expect(page.getByRole("heading", { name: CODE, level: 1 })).toBeVisible();
        await expect(page.getByText("E2E notification renamed", { exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Notification Numbers" })).toHaveAttribute("href", "/masters/notification-numbers");
        await page.getByRole("tab", { name: "History" }).click();
        // The middleware writes the log on a background thread: poll, then expect exactly the one edit.
        await expect.poll(async () => (await authGet<unknown[]>(page,
            `masters/activity-logs/?changes_only=1&endpoint=${encodeURIComponent(`/api/masters/notification-numbers/${CODE}/`)}`)).body?.length ?? 0,
        ).toBe(1);
        await page.reload({ waitUntil: "networkidle" });
        await page.getByRole("tab", { name: "History" }).click();
        // One timeline entry: the real UPDATE, by the signed-in user (tone is announced as sr-only text).
        await expect(page.getByRole("listitem").filter({ hasText: /^Updated/ }).filter({ hasText: "hardik" })).toHaveCount(1);

        await page.goto("/masters/notification-numbers", { waitUntil: "networkidle" });
        await searchUntilOnly(page, "E2E/99");
        await rowAction(page, "Delete");
        await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
        await expect(page.getByText(CODE, { exact: true })).toHaveCount(0);
        expect((await authGet(page, `masters/notification-numbers/${encodeURIComponent(CODE)}/`)).status).toBe(404);
    });

    test("create and find a port (pk-keyed master)", async ({ page }) => {
        await signIn(page);
        await page.goto("/masters/ports/create", { waitUntil: "networkidle" });
        await page.locator("#field-code").fill(PORT_CODE);
        await page.locator("#field-name").fill("E2E Browser Port");
        await page.getByRole("button", { name: "Create" }).click();
        await page.waitForURL(/\/masters\/ports$/);
        await page.getByPlaceholder(/Search by/).first().fill("E2E Browser Port");
        await expect(page.getByText(PORT_CODE, { exact: true })).toBeVisible();
        const listed = await authGet<{ count: number }>(page, `masters/ports/?search=${PORT_CODE}`);
        expect(listed.body?.count).toBe(1);
    });

    test("hub, list and record page fit a phone viewport; desktop comparison screenshots", async ({ page }, testInfo) => {
        await signIn(page);
        await page.setViewportSize({ width: 390, height: 844 });
        const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
        for (const path of ["/masters", "/masters/ports"]) {
            await page.goto(path, { waitUntil: "networkidle" });
            await expect.poll(noOverflow).toBeTruthy();
        }
        await page.screenshot({ path: testInfo.outputPath("masters-ports-list-390.png"), fullPage: true });
        await page.getByRole("link", { name: PORT_CODE, exact: true }).click();
        await expect(page.getByRole("heading", { name: PORT_CODE, level: 1 })).toBeVisible();
        await expect.poll(noOverflow).toBeTruthy();
        await page.screenshot({ path: testInfo.outputPath("masters-port-detail-390.png"), fullPage: true });

        // Same session (the login endpoint is rate limited): desktop screenshots for a side-by-side with the licence register.
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto("/licenses", { waitUntil: "networkidle" });
        await page.screenshot({ path: testInfo.outputPath("licences-1440.png") });
        await page.goto("/masters/ports", { waitUntil: "networkidle" });
        await expect(page.getByRole("list", { name: "Ports" })).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("masters-ports-1440.png") });
        await page.getByRole("link", { name: PORT_CODE, exact: true }).click();
        await expect(page.getByRole("heading", { name: PORT_CODE, level: 1 })).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("masters-port-detail-1440.png") });

        // Same row metrics as the licence register (live UI measured: 50 px rows, 10 px radius, slate-300 border).
        const rowStyle = (selector: string) => page.locator(selector).first().evaluate((el) => {
            const cs = getComputedStyle(el);
            return { h: Math.round(el.getBoundingClientRect().height), radius: cs.borderRadius, border: cs.borderTopColor, font: cs.fontFamily.split(",")[0] };
        });
        await page.goto("/masters/ports", { waitUntil: "networkidle" });
        const masterRow = await rowStyle('ul[aria-label="Ports"] > li > article');
        await page.goto("/licenses", { waitUntil: "networkidle" });
        const licenceRow = await rowStyle('ul[aria-label="Licenses"] > li > article');
        expect({ radius: masterRow.radius, border: masterRow.border, font: masterRow.font }).toEqual({ radius: licenceRow.radius, border: licenceRow.border, font: licenceRow.font });
        expect(Math.abs(masterRow.h - licenceRow.h)).toBeLessThanOrEqual(6);

        // One toolbar row like the licence register: breadcrumb, h1, count, search, Filters, Excel, PDF, Add New.
        const toolbarRow = async () => page.evaluate(() => {
            const mid = (el: Element | null) => (el ? Math.round(el.getBoundingClientRect().top + el.getBoundingClientRect().height / 2) : null);
            const q = (sel: string) => document.querySelector(sel);
            return {
                h1: mid(q("h1")),
                search: mid(q("input[placeholder^='Search']")),
                filters: mid(Array.from(document.querySelectorAll("button")).find(b => b.textContent?.trim().startsWith("Filters")) ?? null),
                excel: mid(q("[aria-label='Export to Excel']")),
                addNew: mid(q("[aria-label='Add New']")),
                filterPanelHidden: (q("section[aria-label='Filters']") as HTMLElement | null)?.hidden ?? true,
            };
        });
        const licenceToolbar = await toolbarRow();
        // Filters appear exactly where the master has filters configured (Ports has none, so no empty control).
        for (const [entity, hasFilters] of [["companies", true], ["ports", false], ["item-names", true]] as const) {
            await page.goto(`/masters/${entity}`, { waitUntil: "networkidle" });
            await expect(page.getByRole("list").first()).toBeVisible();
            const t = await toolbarRow();
            expect(t.filters !== null, `${entity}: Filters control only when the master has filters`).toBe(hasFilters);
            const ys = [t.h1, t.search, t.filters, t.excel, t.addNew].filter((y): y is number => y !== null);
            expect(ys.length, `${entity}: toolbar controls present`).toBe(hasFilters ? 5 : 4);
            expect(Math.max(...ys) - Math.min(...ys), `${entity}: one toolbar row`).toBeLessThanOrEqual(8);
            expect(Math.abs(t.h1! - licenceToolbar.h1!), `${entity}: toolbar at the licence position`).toBeLessThanOrEqual(4);
            expect(t.filterPanelHidden, `${entity}: filters closed by default`).toBe(true);
            await page.screenshot({ path: testInfo.outputPath(`compare-${entity}-1440.png`) });
        }
        // Companies: identifier is the IEC (not a timestamp); a row expands to its address in place.
        await page.goto("/masters/companies", { waitUntil: "networkidle" });
        const companyRows = page.getByRole("list", { name: "Companies" }).getByRole("listitem");
        await expect(companyRows.first().getByRole("link").first()).toHaveText(/^\d{10}$/);
        await companyRows.first().getByRole("button", { name: /^Expand / }).click();
        await expect(companyRows.first().getByRole("region")).toBeVisible();
        await page.getByRole("button", { name: /^Filters/ }).click();
        await expect(page.locator("section[aria-label='Filters']")).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("compare-companies-filters-open-1440.png") });
    });

    test("Masters menu: two columns, every registered master once, each opens its workspace and a record", async ({ page }, testInfo) => {
        await signIn(page);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto("/masters", { waitUntil: "networkidle" });
        const trigger = page.locator("[data-nav-trigger]", { hasText: "Masters" });
        await trigger.click();
        const menu = page.getByRole("menu");
        await expect(menu).toBeVisible();
        const entries = await menu.getByRole("menuitem").evaluateAll(items => items.map(a => ({
            href: a.getAttribute("href"), label: a.textContent?.trim(), x: Math.round(a.getBoundingClientRect().left),
        })));
        const hrefs = entries.map(e => e.href);
        expect(new Set(hrefs).size, "no duplicate entries").toBe(hrefs.length);
        expect(hrefs).toEqual(expect.arrayContaining([
            "/masters", "/masters/companies", "/masters/ports", "/masters/hs-codes", "/masters/head-norms", "/masters/sion-classes",
            "/masters/groups", "/masters/item-names", "/masters/scheme-codes", "/masters/notification-numbers",
            "/masters/purchase-statuses", "/masters/transfer-letters", "/masters/exchange-rates", "/masters/unit-prices",
        ]));
        expect(hrefs).toHaveLength(14);
        expect(new Set(entries.map(e => e.x)).size, "two columns").toBe(2);
        const box = await menu.boundingBox();
        expect(box!.x + box!.width).toBeLessThanOrEqual(1440);
        await page.screenshot({ path: testInfo.outputPath("masters-menu-1440.png") });
        await page.keyboard.press("Escape");
        await expect(menu).toBeHidden();

        // Keyboard: ArrowDown on the trigger opens the menu and focuses its first entry.
        await trigger.focus();
        await page.keyboard.press("ArrowDown");
        await expect(page.getByRole("menuitem").first()).toBeFocused();
        await page.keyboard.press("Escape");

        for (const { href, label } of entries) {
            await page.goto(href!, { waitUntil: "networkidle" });
            await expect(page.getByRole("heading", { level: 1 }), `${href} title`).toHaveText(href === "/masters" ? "Masters" : label!);
            if (href === "/masters") continue;
            const list = page.getByRole("list", { name: label! });
            const empty = page.getByText(/^No .* found$/);
            await expect(list.or(empty), `${href} renders rows or the empty state`).toBeVisible();
            if (await list.isVisible()) {
                await list.getByRole("listitem").first().getByRole("link").first().click();
                await expect(page.getByRole("link", { name: label!, exact: true }), `${href} record breadcrumb`).toBeVisible();
                await expect(page.getByRole("tab", { name: "Details" })).toBeVisible();
            }
        }

        // Phone width: the menu still opens and nothing overflows horizontally.
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto("/masters", { waitUntil: "networkidle" });
        const mobileTrigger = page.locator("[data-nav-trigger]", { hasText: "Masters" });
        if (await mobileTrigger.isVisible()) {
            await mobileTrigger.click();
            await expect(page.getByRole("menu")).toBeVisible();
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath("masters-menu-390.png") });
    });

    test("bulk deactivate and bulk delete report every record and keep referenced data", async ({ page }) => {
        await signIn(page);
        await page.goto("/masters/purchase-statuses", { waitUntil: "networkidle" });
        for (const code of ["Y1", "Y2"]) {
            expect((await authPost(page, "masters/purchase-statuses/", { code, label: `E2E Bulk ${code}`, is_active: true, display_order: 990 })).status).toBe(201);
        }
        await page.reload({ waitUntil: "networkidle" });
        await page.getByPlaceholder(/Search by/).first().fill("E2E Bulk");
        const list = page.getByRole("list", { name: "Purchase Statuses" });
        await expect(list.getByRole("listitem")).toHaveCount(2);
        await page.getByRole("checkbox", { name: "Select all on page" }).click();
        await expect(page.getByText("2 selected")).toBeVisible();
        await page.getByRole("button", { name: "Deactivate" }).click();
        await page.getByRole("alertdialog").getByRole("button", { name: "Deactivate" }).click();
        await expect(page.getByTestId("bulk-results")).toContainText("2 of 2 deactivated");
        await expect(list.getByText("Inactive")).toHaveCount(2);
        const statuses = await authGet<{ results: { code: string; is_active: boolean; id: number }[] }>(page, "masters/purchase-statuses/?search=E2E%20Bulk");
        expect(statuses.body?.results.map(r => r.is_active)).toEqual([false, false]);
        // Each bulk change is in that record's own history, like a single edit.
        const first = statuses.body!.results[0];
        const history = await authGet<{ action: string }[]>(page,
            `masters/activity-logs/?changes_only=1&endpoint=${encodeURIComponent(`/api/masters/purchase-statuses/${first.id}/`)}`);
        expect(history.body?.map(r => r.action)).toContain("UPDATE");

        // Ports: the seeded port is used by licences and must survive; the unused one is deleted.
        await page.goto("/masters/ports", { waitUntil: "networkidle" });
        await page.getByPlaceholder(/Search by/).first().fill("E2E");
        const ports = page.getByRole("list", { name: "Ports" });
        await expect(ports.getByRole("listitem")).toHaveCount(2);
        await page.getByRole("checkbox", { name: "Select all on page" }).click();
        await page.getByRole("button", { name: "Delete" }).click();
        await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
        const results = page.getByTestId("bulk-results");
        await expect(results).toContainText("1 of 2 deleted");
        await expect(results).toContainText("still referenced");
        await expect(ports.getByRole("listitem")).toHaveCount(1);
        expect((await authGet<{ count: number }>(page, `masters/ports/?search=${PORT_CODE}`)).body?.count).toBe(0);
        expect((await authGet<{ count: number }>(page, "masters/ports/?search=E2E")).body?.count).toBe(1);
    });
});
