import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND — generic master record page (tabs + accordion) and the Transfer Letter DOCX viewer.
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/masters-detail.real.spec.ts`
 * (fresh `test_*` database, seeded, superuser). The transfer letter is an isolated record this spec
 * uploads with the real reference template `backend/media/tl/LABDHI_NEW.docx`.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const AUTH_STATE = "test-results/.masters-detail-auth.json";
const RUN = Date.now().toString().slice(-6);
const DOCX_PATH = fileURLToPath(new URL("../../backend/media/tl/LABDHI_NEW.docx", import.meta.url));

const MASTERS = [
    "companies", "ports", "hs-codes", "head-norms", "sion-classes", "groups", "item-names",
    "scheme-codes", "notification-numbers", "purchase-statuses", "transfer-letters", "exchange-rates", "unit-prices",
];

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function noHorizontalOverflow(page: Page) {
    return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
}

test.describe("Master record pages: generic tabs, accordion and DOCX viewer (real backend)", () => {
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

    test("Transfer Letter: the record's DOCX renders in the Document tab, downloads, and keeps ?tab=details", async ({ page }, testInfo) => {
        await page.goto("/masters/transfer-letters", { waitUntil: "networkidle" });
        const base64 = readFileSync(DOCX_PATH).toString("base64");
        const created = await page.evaluate(async ([name, data]) => {
            const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
            const form = new FormData();
            form.append("name", name);
            form.append("tl", new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }), `E2E_TL_${name.split(" ").pop()}.docx`);
            const response = await fetch("/api/masters/transfer-letters/", {
                method: "POST",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
                body: form,
            });
            return { status: response.status, body: response.ok ? await response.json() : await response.text() };
        }, [`E2E TL ${RUN}`, base64] as const);
        expect(created.status, JSON.stringify(created.body).slice(0, 300)).toBe(201);
        const record = created.body as { id: number; tl: string };
        const filename = decodeURIComponent(record.tl.split("/").pop()!);

        // Existing deep link still lands on Details; the accordion sections are real and collapsible.
        await page.goto(`/masters/transfer-letters/${record.id}?tab=details`, { waitUntil: "networkidle" });
        await expect(page.getByRole("tab", { name: "Details", selected: true })).toBeVisible();
        const general = page.getByRole("button", { name: "General information" });
        await expect(general).toHaveAttribute("aria-expanded", "true");
        await general.click();
        await expect(general).toHaveAttribute("aria-expanded", "false");
        await general.click();

        // Document tab: actual contents (the template's table) rendered in the page.
        // Record tabs are panel state (licence pattern); ?tab= is only read when the record is opened by URL.
        await page.getByRole("tab", { name: "Documents" }).click();
        await expect(page.getByRole("button", { name: `Download ${filename}` })).toBeVisible();
        const doc = page.getByRole("document", { name: `${filename} preview` });
        await expect(doc.getByText("DFIA No & Date")).toBeVisible({ timeout: 20_000 });
        await expect(doc.getByText("Exporter Name")).toBeVisible();
        await expect(doc.locator("table")).toHaveCount(1);
        await expect(doc.locator("section.docx").first()).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("tl-document-1440.png"), fullPage: false });

        // Zoom changes the rendered size.
        const before = (await doc.locator("section.docx").first().boundingBox())!.width;
        await page.getByRole("button", { name: "Zoom in" }).click();
        await expect(page.getByText("110%")).toBeVisible();
        await expect.poll(async () => (await doc.locator("section.docx").first().boundingBox())!.width).toBeGreaterThan(before);

        // Download returns the original file (same bytes) under its stored name.
        const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download", exact: true }).click()]);
        expect(download.suggestedFilename()).toBe(filename);
        const saved = readFileSync((await download.path())!);
        expect(saved.equals(readFileSync(DOCX_PATH)), "downloaded bytes equal the stored DOCX").toBe(true);

        // The media request is authenticated: without a token the same file is refused.
        const anonymous = await page.evaluate(async url => (await fetch(url)).status, `/api/media/tl/${encodeURIComponent(filename)}`);
        expect([401, 403]).toContain(anonymous);

        // Phone width: the viewer scrolls inside its frame, the page does not overflow.
        await page.setViewportSize({ width: 390, height: 844 });
        await expect(doc.getByText("DFIA No & Date")).toBeVisible();
        expect(await noHorizontalOverflow(page)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath("tl-document-390.png") });

        // Remove the isolated record (the uploaded file itself stays in MEDIA_ROOT; Django does not purge files).
        const removed = await page.evaluate(async id => (await fetch(`/api/masters/transfer-letters/${id}/`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
        })).status, record.id);
        expect(removed).toBe(204);
    });

    test("every registered master: record page has generic tabs and collapsible accordion sections", async ({ page }) => {
        for (const entity of MASTERS) {
            await page.goto(`/masters/${entity}`, { waitUntil: "networkidle" });
            const firstLink = page.locator("ul[aria-label] > li").first().getByRole("link").first();
            if (!(await firstLink.isVisible())) continue; // empty seeded master: list shows its empty state
            await firstLink.click();
            await expect(page.getByRole("tab", { name: "Overview" }), `${entity}: Overview tab`).toBeVisible();
            await expect(page.getByRole("tab", { name: "Overview", selected: true }), `${entity}: Overview is the default`).toBeVisible();
            await expect(page.getByRole("tab", { name: "History" }), `${entity}: History tab (superuser)`).toBeVisible();
            await page.getByRole("tab", { name: "Details" }).click();
            const general = page.getByRole("button", { name: "General information" });
            await expect(general, `${entity}: General information section`).toBeVisible();
            const expanded = await general.getAttribute("aria-expanded");
            await general.click();
            await expect(general).toHaveAttribute("aria-expanded", expanded === "true" ? "false" : "true");
            await general.click();
            if (entity === "sion-classes") {
                const related = page.getByRole("tab", { name: /Related records/ });
                if (await related.isVisible()) {
                    await related.click();
                    await expect(page.getByRole("region").first()).toBeVisible();
                }
            }
            await page.getByRole("tab", { name: "History" }).click();
            const record = page.getByRole("region", { name: / details$/ });
            await expect(record.getByText(/No recorded changes|Updated|Created|Deleted/).first(), `${entity}: history state`).toBeVisible();
            expect(await noHorizontalOverflow(page), `${entity}: no horizontal overflow`).toBe(true);
        }
    });

    test("Exchange Rates: Open record expands inline — no page navigation, collapse returns to the list", async ({ page }, testInfo) => {
        // Isolated record (exchange-rate dates are unique; the seed may have none).
        await page.goto("/masters/exchange-rates?page=1", { waitUntil: "networkidle" });
        const date = `2098-${String(1 + (Number(RUN) % 12)).padStart(2, "0")}-${String(1 + (Number(RUN) % 28)).padStart(2, "0")}`;
        const created = await page.evaluate(async body => (await fetch("/api/masters/exchange-rates/", {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access")}` },
            body: JSON.stringify(body),
        })).status, { date, usd: "84.1234", euro: "91.5678", pound_sterling: "107.0001", chinese_yuan: "11.6789" });
        expect(created).toBe(201);
        await page.reload({ waitUntil: "networkidle" });
        const list = page.getByRole("list", { name: "Exchange Rates" });
        const row = list.getByRole("listitem").first();
        await expect(row).toBeVisible();
        const identifier = (await row.getByRole("link").first().textContent())!.trim();
        // Mark the live list node: a page navigation or remount would drop the mark.
        await list.evaluate(el => { (el as HTMLElement & { __kept?: boolean }).__kept = true; });

        await row.getByRole("button", { name: `Actions for ${identifier}` }).click();
        await page.getByRole("menuitem", { name: "Open record" }).click();
        const region = page.getByRole("region", { name: `${identifier} details` });
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
        await expect(page).toHaveURL(/\/masters\/exchange-rates\/\d+\?(.*&)?page=1/);
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("Exchange Rates");
        expect(await list.evaluate(el => (el as HTMLElement & { __kept?: boolean }).__kept === true), "same list node: no navigation").toBe(true);
        // Real values, as stored (no rounding), in the inline record.
        await region.getByRole("tab", { name: "Details" }).click();
        await expect(region.getByRole("button", { name: "General information" })).toBeVisible();
        expect(await noHorizontalOverflow(page)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath("exchange-rate-inline-1440.png") });

        // Edit tab: the real form inline; save updates the record without leaving the list.
        await region.getByRole("tab", { name: "Edit" }).click();
        await expect(region.locator("#field-usd")).toBeVisible();
        await region.locator("#field-usd").fill("84.4321");
        await region.getByRole("button", { name: "Update" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
        await expect(region.getByText("84.4321", { exact: true })).toBeVisible();
        expect(await list.evaluate(el => (el as HTMLElement & { __kept?: boolean }).__kept === true), "saved without navigation").toBe(true);
        await expect(page).toHaveURL(/\/masters\/exchange-rates\/\d+\?(.*&)?page=1/);
        // History: the real UPDATE the server logged (written on a background thread).
        await region.getByRole("tab", { name: "History" }).click();
        await expect(region.getByText("Updated").first()).toBeVisible({ timeout: 15_000 });

        // Validation stays inline: a negative rate is refused (MinValueValidator(0)) and shown in the form.
        await region.getByRole("tab", { name: "Edit" }).click();
        await region.locator("#field-usd").fill("-1");
        await region.getByRole("button", { name: "Update" }).click();
        await expect(region.getByText(/Validation Error|greater than or equal to 0/i).first()).toBeVisible();
        await region.getByRole("button", { name: "Cancel" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

        // Collapse returns to the compact list; reopen works.
        await row.getByRole("button", { name: `Collapse ${identifier}` }).click();
        await expect(region).toHaveCount(0);
        await expect(page).toHaveURL(/\/masters\/exchange-rates\?(.*&)?page=1/);
        await row.getByRole("button", { name: `Expand ${identifier}` }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

        // Old edit-page URL: the list with this record open on its Edit tab.
        const id = new URL(page.url()).pathname.split("/").pop();
        await page.goto(`/masters/exchange-rates/${id}/edit`, { waitUntil: "networkidle" });
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("Exchange Rates");
        await expect(page.getByRole("region", { name: `${identifier} details` }).getByRole("tab", { name: "Edit", selected: true })).toBeVisible();
        await expect(page).toHaveURL(new RegExp(`/masters/exchange-rates/${id}(\\?|$)`));
    });

    test("Item Names: inline record keeps filters, page and scroll; survives refresh; back/forward close and reopen it", async ({ page }) => {
        await page.goto("/masters/item-names?is_active=true&page=2", { waitUntil: "networkidle" });
        const all = await page.evaluate(async () => (await (await fetch("/api/masters/item-names/?is_active=true&page_size=1", {
            headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
        })).json()).count as number);
        test.skip(all <= 25, "needs more than one page of active item names");
        const list = page.getByRole("list", { name: "Item Names" });
        const rows = list.getByRole("listitem");
        await expect(rows.first()).toBeVisible();
        const target = rows.nth(Math.min(10, (await rows.count()) - 1));
        const identifier = (await target.getByRole("link").first().textContent())!.trim();
        await target.scrollIntoViewIfNeeded();
        const scrollBefore = await page.evaluate(() => window.scrollY);

        await target.getByRole("link", { name: identifier, exact: true }).click();
        const region = page.getByRole("region", { name: `${identifier} details` });
        await expect(region.getByRole("tab", { name: "Overview" })).toBeVisible();
        const url = new URL(page.url());
        expect(url.pathname).toMatch(/^\/masters\/item-names\/[^/]+$/);
        expect(url.searchParams.get("is_active")).toBe("true");
        expect(url.searchParams.get("page")).toBe("2");
        // Expanding grows the row below the fold; the viewport does not jump.
        expect(Math.abs((await page.evaluate(() => window.scrollY)) - scrollBefore)).toBeLessThanOrEqual(40);

        await page.reload({ waitUntil: "networkidle" });
        await expect(page.getByRole("region", { name: `${identifier} details` }).getByRole("tab", { name: "Overview" })).toBeVisible();
        await expect(page.getByRole("navigation", { name: "Pagination" }).getByRole("button", { name: "Page 2", exact: true })).toHaveAttribute("aria-current", "page");

        await page.goBack({ waitUntil: "networkidle" });
        await expect(page.getByRole("region", { name: `${identifier} details` })).toHaveCount(0);
        expect(new URL(page.url()).pathname).toBe("/masters/item-names");
        expect(new URL(page.url()).searchParams.get("page")).toBe("2");
        await page.goForward({ waitUntil: "networkidle" });
        await expect(page.getByRole("region", { name: `${identifier} details` }).getByRole("tab", { name: "Overview" })).toBeVisible();
    });
});
