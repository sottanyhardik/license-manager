import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND — the one-page Licence Ledger: Category → Company accordion → SION accordion → licence row →
 * inline licence workspace (Overview / Ledger / BOE & Allotments / Invoices / Documents / Edit / History).
 * The former `/license-ledger/:licenseId/:itemId` page URLs open the same page with the licence expanded.
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/licence-ledger-onepage.real.spec.ts`
 * (fresh `test_*` database, `seed_browser_2509`: licence 3411008090 / id 2509 with a purchase + sale, superuser).
 * Nothing is saved: the edit check stops at the server-side/form validation.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const LICENCE = "3411008090";
const LICENCE_ID = 2509;

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function apiGet<T>(page: Page, path: string): Promise<T> {
    return page.evaluate(async url => (await fetch(`/api/${url}`, { headers: { Authorization: `Bearer ${localStorage.getItem("access")}` } })).json(), path);
}

test.describe("One-page Licence Ledger (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");

    test("accordions, inline licence workspace with real data in every tab, documents, edit validation, old URLs, back/forward", async ({ page }, testInfo) => {
        await signIn(page);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto("/license-ledger", { waitUntil: "networkidle" });
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("License Ledger");
        const list = page.getByTestId("company-sion-ledger");
        await list.evaluate(el => { (el as HTMLElement & { __kept?: boolean }).__kept = true; });

        // Level 2/3 — company and SION accordions expand and collapse.
        const company = page.getByRole("button", { name: /^E2E Browser Exporter/ });
        await expect(company).toHaveAttribute("aria-expanded", "true");
        await company.click();
        await expect(company).toHaveAttribute("aria-expanded", "false");
        await expect(page.getByRole("button", { name: LICENCE, exact: true })).toBeHidden();
        await company.click();
        const sion = page.getByRole("button", { name: /^SION: / }).first();
        await sion.click();
        await expect(sion).toHaveAttribute("aria-expanded", "false");
        await sion.click();
        await expect(sion).toHaveAttribute("aria-expanded", "true");

        // Level 4/5 — the licence row opens its workspace inline; the page never changes.
        await page.getByRole("button", { name: LICENCE, exact: true }).click();
        await expect(page).toHaveURL(new RegExp(`/license-ledger/${LICENCE_ID}/\\d+$`));
        const companyId = new URL(page.url()).pathname.split("/").pop()!;
        const workspace = page.getByRole("region", { name: `Licence ${LICENCE} workspace` });
        await expect(workspace).toBeVisible();
        expect(await list.evaluate(el => (el as HTMLElement & { __kept?: boolean }).__kept === true), "same page, no navigation").toBe(true);
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("License Ledger");

        // Overview = the former detail page's header + reconciliation summary, from the same API.
        const detail = await apiGet<{ license_number: string; transactions: unknown[] }>(page, `license-ledger/${LICENCE_ID}/ledger_detail/?company=${companyId}`);
        expect(detail.license_number).toBe(LICENCE);
        await expect(workspace.getByText(LICENCE).first()).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("ledger-onepage-overview-1440.png"), fullPage: true });

        // Ledger = the transaction tables (purchase + sale rows).
        await workspace.getByRole("tab", { name: "Ledger", exact: true }).click();
        await expect(workspace.getByText(/Purchase|Sale/).first()).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath("ledger-onepage-ledger-1440.png"), fullPage: true });

        // BOE & Allotments / Invoices / History — the licence register's own tabs and endpoints.
        await workspace.getByRole("tab", { name: "BOE & Allotments" }).click();
        await expect(workspace.getByRole("button", { name: "Bills of Entry" })).toBeVisible();
        await expect(workspace.getByRole("button", { name: "Allotments" })).toBeVisible();
        await workspace.getByRole("tab", { name: "Invoices" }).click();
        await expect(workspace.getByRole("tabpanel")).not.toBeEmpty();
        await workspace.getByRole("tab", { name: "History" }).click();
        await expect(workspace.getByRole("tabpanel")).not.toBeEmpty();

        // Documents — ledger PDF (authenticated preview), Excel, customs ledger PDF, licence copy.
        await workspace.getByRole("tab", { name: "Documents" }).click();
        const pdfResponse = page.waitForResponse(r => r.url().includes("license-ledger/export/") && r.url().includes("pdf"));
        const [popup] = await Promise.all([page.waitForEvent("popup"), workspace.getByRole("button", { name: "Preview ledger PDF" }).click()]);
        const pdf = await pdfResponse;
        expect(pdf.status()).toBe(200);
        expect(pdf.headers()["content-type"]).toContain("pdf");
        await popup.close();
        const [excel] = await Promise.all([page.waitForEvent("download", { timeout: 60_000 }), workspace.getByRole("button", { name: "Download ledger Excel" }).click()]);
        expect(excel.suggestedFilename()).toMatch(/\.xlsx$/);
        await expect(workspace.getByRole("button", { name: "Download customs ledger PDF" })).toBeVisible();

        // Edit — the licence form inline; validation is shown in place and nothing is saved.
        await workspace.getByRole("tab", { name: "Edit" }).click();
        await expect(workspace.locator("#field-license_number")).toHaveValue(LICENCE, { timeout: 15_000 });
        await workspace.locator("#field-license_number").fill("");
        await workspace.getByRole("button", { name: "Update" }).click();
        await expect(workspace.getByText(/Validation Error|required/i).first()).toBeVisible();
        expect((await apiGet<{ license_number: string }>(page, `licenses/${LICENCE_ID}/`)).license_number).toBe(LICENCE);
        await workspace.getByRole("button", { name: "Cancel" }).click();
        await expect(workspace.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

        // Back closes the licence (same page); forward reopens it.
        await page.goBack();
        await expect(workspace).toHaveCount(0);
        await expect(page).toHaveURL(/\/license-ledger$/);
        await page.goForward();
        await expect(page.getByRole("region", { name: `Licence ${LICENCE} workspace` })).toBeVisible();

        // Old detail URL (deep link + ?tab) → this page, groups shown, licence expanded on the Ledger tab; survives refresh.
        await page.goto(`/license-ledger/${LICENCE_ID}/${companyId}?tab=ledger`, { waitUntil: "networkidle" });
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("License Ledger");
        const opened = page.getByRole("region", { name: `Licence ${LICENCE} workspace` });
        await expect(opened.getByRole("tab", { name: "Ledger", exact: true, selected: true })).toBeVisible();
        await expect(page.getByRole("button", { name: /^E2E Browser Exporter/ })).toHaveAttribute("aria-expanded", "true");
        await page.reload({ waitUntil: "networkidle" });
        await expect(page.getByRole("region", { name: `Licence ${LICENCE} workspace` })).toBeVisible();

        // Single-segment old URL works too; Close returns to the plain ledger.
        await page.goto(`/license-ledger/${LICENCE_ID}`, { waitUntil: "networkidle" });
        const single = page.getByRole("region", { name: `Licence ${LICENCE} workspace` });
        await expect(single).toBeVisible();
        await single.getByRole("button", { name: `Collapse licence ${LICENCE}` }).click();
        await expect(page).toHaveURL(/\/license-ledger$/);

        // Phone width: the workspace scrolls inside, the page does not overflow.
        await page.goto(`/license-ledger/${LICENCE_ID}/${companyId}`, { waitUntil: "networkidle" });
        await page.setViewportSize({ width: 390, height: 844 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.screenshot({ path: testInfo.outputPath("ledger-onepage-390.png"), fullPage: true });
    });
});
