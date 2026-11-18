import { expect, test } from "@playwright/test";
import fs from "node:fs";

/**
 * LIVE, READ-ONLY check of the E126 Vegetable Oil entitlement split for licence
 * 3411008089 (id 2510) on the local dev stack.  Every non-GET /api request is
 * aborted and the test asserts none was attempted.
 *
 * Needs a saved session:
 *   npx playwright codegen --save-storage=/tmp/lm_auth/state.json http://localhost:5173/login
 * Run:
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test -c playwright.live.config.ts e2e/e126-entitlement.live.spec.ts
 */
const STATE = process.env.LM_AUTH_STATE || "/tmp/lm_auth/state.json";
const LICENCE_ID = process.env.LM_E126_LICENCE_ID || "2510";
const LICENCE_NO = process.env.LM_E126_LICENCE_NO || "3411008089";
const OUT = process.env.LM_LIVE_SHOTS || "/tmp/lm_browser/out";
const haveState = fs.existsSync(STATE);
const state = haveState ? JSON.parse(fs.readFileSync(STATE, "utf8")) : { cookies: [], origins: [] };
const storage: { name: string; value: string }[] = (state.origins || []).flatMap((o: { localStorage?: { name: string; value: string }[] }) => o.localStorage || []);

test.skip(!haveState, `Auth state missing: create ${STATE} with "npx playwright codegen --save-storage=${STATE} http://localhost:5173/login"`);
test.use({ viewport: { width: 1440, height: 900 } });

test.beforeEach(async ({ page }) => {
    await page.context().addCookies(state.cookies || []);
    await page.addInitScript((entries: { name: string; value: string }[]) => {
        for (const { name, value } of entries) localStorage.setItem(name, value);
    }, storage);
});

async function blockWrites(page: import("@playwright/test").Page) {
    const blocked: string[] = [];
    await page.route("**/api/**", (route) => {
        const req = route.request();
        if (req.method() !== "GET") { blocked.push(`${req.method()} ${req.url()}`); return route.abort(); }
        return route.continue();
    });
    return blocked;
}

test("Auto Plan shows PKO and OLIVE OIL children with their own balances", async ({ page }) => {
    const blocked = await blockWrites(page);
    await page.goto(`/licenses/${LICENCE_ID}/overview?tab=planning`);
    await page.getByRole("button", { name: /expand|split|RELEVANT FATS/i }).first().click().catch(() => undefined);
    await expect(page.getByText("PALM KERNEL OIL", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("OLIVE OIL", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("14,039.130")).toBeVisible();
    await expect(page.getByText("169,077.490")).toBeVisible();
    await expect(page.getByText("PARTIALLY UTILIZED")).toHaveCount(2);
    fs.mkdirSync(OUT, { recursive: true });
    await page.screenshot({ path: `${OUT}/e126-autoplan-children.png`, fullPage: true });
    expect(blocked).toEqual([]);
});

test("Planning report reproduces the spreadsheet sections", async ({ page }) => {
    const blocked = await blockWrites(page);
    await page.goto(`/planning?license=${LICENCE_NO}&sion=E126&view=simulation`);
    await expect(page.getByText("OPENING PLANNING")).toBeVisible();
    await expect(page.getByText("AFTER BOE DEBITS AND ALLOTTED")).toBeVisible();
    for (const figure of ["8,09,379.86", "7,66,458.23", "21,49,051.85", "25,270.43", "14,039.13", "1,69,077.49"]) {
        await expect(page.getByText(figure).first()).toBeVisible();
    }
    await page.screenshot({ path: `${OUT}/e126-planning-report.png`, fullPage: true });
    expect(blocked).toEqual([]);
});
