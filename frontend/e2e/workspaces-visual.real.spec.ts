import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND — visual + structural comparison of the five ERP workspaces against the Licence register.
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/workspaces-visual.real.spec.ts`.
 * Captures 1440 / 390 screenshots and measures the page toolbar (breadcrumb, H1, search, Filters, export,
 * create) so every workspace is compared with the same numbers as the Licence reference.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const AUTH_STATE = "test-results/.workspaces-visual-auth.json";

export const WORKSPACES = [
    { id: "licences", path: "/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=10%2C12%2C13%2C14%2C11%2C1%2C9", title: "Licenses" },
    { id: "ledger-upload", path: "/ledger-upload", title: "Ledger Upload" },
    { id: "license-ledger", path: "/license-ledger", title: "License Ledger" },
    { id: "planning", path: "/planning", title: "Planning" },
    { id: "incentive-licenses", path: "/incentive-licenses?page=1", title: "Incentive Licenses" },
] as const;

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

/** Geometry of the page header toolbar (null = control absent). */
async function measure(page: Page) {
    return page.evaluate(() => {
        const box = (el: Element | null | undefined) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return r.width === 0 && r.height === 0 ? null : { top: Math.round(r.top), h: Math.round(r.height), mid: Math.round(r.top + r.height / 2) };
        };
        const h1 = document.querySelector("main h1, h1");
        return {
            h1: box(h1),
            h1Text: h1?.textContent?.trim() ?? null,
            h1Font: h1 ? getComputedStyle(h1).fontSize : null,
            breadcrumb: box(document.querySelector("nav[aria-label='Breadcrumb']")),
            search: box(document.querySelector("input[placeholder^='Search']")),
            filters: box(Array.from(document.querySelectorAll("button")).find(b => b.textContent?.trim().startsWith("Filters"))),
            scrollOverflow: document.documentElement.scrollWidth > window.innerWidth,
        };
    });
}

test.describe("Workspace visual comparison (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");
    test.describe.configure({ mode: "serial" });
    test.use({ storageState: AUTH_STATE });
    test.beforeAll(async ({ browser }) => {
        const context = await browser.newContext({ storageState: undefined });
        const page = await context.newPage();
        await signIn(page);
        await context.storageState({ path: AUTH_STATE });
        await context.close();
    });

    test("screenshots and toolbar geometry for every workspace at 1440 and 390", async ({ page }, testInfo) => {
        const rows: Record<string, unknown>[] = [];
        for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
            await page.setViewportSize(viewport);
            for (const w of WORKSPACES) {
                await page.goto(w.path, { waitUntil: "networkidle" });
                await page.waitForTimeout(300);
                const m = await measure(page);
                rows.push({ workspace: w.id, width: viewport.width, ...m });
                await page.screenshot({ path: testInfo.outputPath(`${w.id}-${viewport.width}.png`), fullPage: viewport.width === 1440 });
                expect(m.scrollOverflow, `${w.id} @${viewport.width}: no horizontal page overflow`).toBe(false);
            }
        }
        await testInfo.attach("toolbar-geometry.json", { body: JSON.stringify(rows, null, 2), contentType: "application/json" });
        console.log("GEOMETRY", JSON.stringify(rows));
    });
});
