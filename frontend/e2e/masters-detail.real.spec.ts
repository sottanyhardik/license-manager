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
        await expect(page.getByRole("button", { name: "Attachments and documents" })).toBeVisible();
        await general.click();
        await expect(general).toHaveAttribute("aria-expanded", "false");
        await general.click();

        // Document tab: actual contents (the template's table) rendered in the page.
        await page.getByRole("tab", { name: "Document" }).click();
        await expect(page).toHaveURL(/tab=document/);
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
            await expect(page).toHaveURL(/tab=details/);
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
            await expect(page.getByText(/No recorded changes|Updated|Created|Deleted/).first(), `${entity}: history state`).toBeVisible();
            expect(await noHorizontalOverflow(page), `${entity}: no horizontal overflow`).toBe(true);
        }
    });
});
