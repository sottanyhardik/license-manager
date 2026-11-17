import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND ACCOUNTING WORKFLOW (opt-in).
 *
 *   LM_E2E_SEED=seed_accounting_e2e scripts/test/run_data_bearing_browser_e2e.sh e2e/accounting.real.spec.ts
 *
 * The harness creates a fresh disposable test_* database, migrates it, seeds it with
 * `seed_accounting_e2e`, and starts an isolated backend + Vite. Never point this at a shared DB.
 */
const enabled = process.env.LM_REAL_E2E === "1" && process.env.LM_E2E_SEED === "seed_accounting_e2e";
const PASSWORD = "e2e-Accounting-2026!";
const ROUTES = [
    "dashboard", "trades", "invoices", "invoices/new", "payments", "vouchers", "vouchers/new", "party-ledger",
    "banking", "banking/workbench", "banking/suspense", "reports/trial-balance", "reports/profit-loss",
    "reports/balance-sheet", "reports/cash-flow", "reports/general-ledger", "reports/receivables-ageing",
    "reports/payables-ageing", "reports/register", "reports/gst", "reports/tds", "reports/trade-profitability",
    "reports/bank-book", "reports/cash-book", "reports/consolidated", "loans", "migration", "setup",
    // frontend round 2026-11-17
    "masters/accounts", "masters/groups", "masters/parties", "ledgers/customers", "ledgers/suppliers", "entities",
    "vouchers/journal", "vouchers/payment", "vouchers/receipt", "vouchers/contra", "vouchers/sales", "vouchers/purchase",
    "banking/transactions", "banking/unmatched", "banking/proposals", "banking/reconciliation", "reports/party-outstanding",
    "reports/voucher-register", "reports/register/expense", "reports/register/sales",
];

async function signIn(page: Page, username: string) {
    await page.context().clearCookies();
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.evaluate(() => localStorage.clear());
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(username);
    await page.locator("#login-password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

function trackErrors(page: Page): string[] {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
        if (m.type() === "error" && !/favicon|403|Forbidden/.test(m.text())) errors.push(m.text());
    });
    return errors;
}

async function chooseEntity(page: Page, name: string) {
    await page.getByRole("combobox", { name: "Entity" }).selectOption({ label: name });
    await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
}

async function confirm(page: Page, button: string) {
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: button, exact: true }).click();
}

test.describe("accounting on a real isolated backend", () => {
    test.skip(!enabled, "Requires the isolated harness with LM_E2E_SEED=seed_accounting_e2e.");
    test.describe.configure({ mode: "serial" });
    test.setTimeout(180_000);

    test("navigation group and every accounting route render", async ({ page }) => {
        const errors = trackErrors(page);
        await signIn(page, "e2e_approver");
        const nav = page.getByRole("navigation", { name: "Main navigation" });
        await nav.getByRole("button", { name: "Accounting", exact: true }).hover();
        await expect(page.getByRole("menuitem", { name: "Trial Balance" })).toBeVisible();
        for (const route of ROUTES) {
            await page.goto(`/accounting/${route}`, { waitUntil: "networkidle" });
            await expect(page.getByText("Accounting", { exact: true }).first()).toBeVisible();
            await expect(page.getByRole("alert").filter({ hasText: /error|failed/i })).toHaveCount(0);
        }
        expect(errors, errors.join("\n")).toEqual([]);
    });

    test("entity and financial-year switching", async ({ page }) => {
        await signIn(page, "e2e_approver");
        await page.goto("/accounting/dashboard", { waitUntil: "networkidle" });
        await chooseEntity(page, "E2E Global LLP");
        await chooseEntity(page, "E2E Mercantile LLP");
        const fy = page.getByRole("combobox", { name: "Financial year" });
        await fy.selectOption("2025-26");
        await expect(fy).toHaveValue("2025-26");
        await fy.selectOption("2026-27");
        await expect(page.getByText("Bank balance")).toBeVisible();
    });

    test("trade to books, receipt, statement upload, reconciliation", async ({ page }) => {
        const errors = trackErrors(page);
        await signIn(page, "e2e_approver");
        await page.goto("/accounting/trades", { waitUntil: "networkidle" });
        await chooseEntity(page, "E2E Mercantile LLP");
        for (const number of ["E2E/PUR/0001", "E2E/SAL/0001", "E2E/IC/0001"]) {
            const row = page.getByRole("row").filter({ hasText: number });
            await row.getByRole("button", { name: "Post to books" }).click();
            await confirm(page, "Post");
            await expect(row.getByText("ACCOUNTED", { exact: true })).toBeVisible();
        }

        await page.goto("/accounting/payments", { waitUntil: "networkidle" });
        await page.getByRole("radio", { name: "Receive from customer" }).click();
        await page.getByRole("combobox", { name: "Party" }).fill("E2E Imp");
        await page.getByRole("option", { name: /E2E Importer Ltd/ }).click();
        await page.getByLabel("Bank / cash").selectOption({ label: "E2E Bank E2E-001" });
        await page.getByLabel("Date").first().fill("2026-05-20");
        await page.getByLabel("Amount through bank").fill("360000.00");
        await page.getByLabel(/UTR/).fill("E2EUTR2026052000001");
        await page.getByRole("button", { name: "Allocate oldest first" }).click();
        await page.getByRole("button", { name: "Post receipt" }).click();
        await confirm(page, "Post");
        await expect(page.getByRole("row").filter({ hasText: "E2EUTR2026052000001" })).toBeVisible();

        await page.goto("/accounting/banking/workbench", { waitUntil: "networkidle" });
        const csv = "Date,Narration,Ref No,Debit,Credit,Balance\n"
            + "20/05/2026,NEFT CR E2E IMPORTER,E2EUTR2026052000001,,360000.00,860000.00\n"
            + "25/05/2026,UNKNOWN CREDIT,,,1000.00,861000.00\n";
        await page.getByLabel("Statement file").setInputFiles({ name: "e2e.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
        await page.getByRole("button", { name: "Import" }).click();
        await expect(page.getByRole("status").filter({ hasText: "2 new" })).toBeVisible();
        await page.getByRole("button", { name: /Auto-match/ }).click();
        await expect(page.getByText(/1 by UTR/)).toBeVisible();
        await page.getByLabel("As of").fill("2026-05-31");
        await expect(page.getByText("Reconciled — difference 0.00")).toBeVisible();
        expect(errors, errors.join("\n")).toEqual([]);
    });

    test("reports balance and drill down to the voucher", async ({ page }) => {
        await signIn(page, "e2e_approver");
        await page.goto("/accounting/reports/trial-balance", { waitUntil: "networkidle" });
        await chooseEntity(page, "E2E Mercantile LLP");
        await expect(page.getByText("MATCHED").first()).toBeVisible();
        await page.getByRole("link", { name: "Licence Sales" }).click();
        await expect(page).toHaveURL(/general-ledger\?account=/);
        await page.getByRole("link", { name: /^SAL\/2026-27\// }).first().click();
        await expect(page).toHaveURL(/\/accounting\/vouchers\/\d+/);
        await expect(page.getByText("Licence Sales").first()).toBeVisible();
        await page.goto("/accounting/reports/balance-sheet", { waitUntil: "networkidle" });
        await expect(page.getByText("MATCHED").first()).toBeVisible();
    });

    test("migration dry run classifies history without posting", async ({ page }) => {
        await signIn(page, "e2e_approver");
        await page.goto("/accounting/migration", { waitUntil: "networkidle" });
        await chooseEntity(page, "E2E Mercantile LLP");
        await page.getByRole("button", { name: "Run dry run" }).click();
        await expect(page.getByText(/Run #\d+ — dry run/)).toBeVisible();
        await expect(page.getByText("ALREADY ACCOUNTED").first()).toBeVisible();
    });

    test("viewer sees no write actions; non-accounting user is kept out", async ({ page }) => {
        await signIn(page, "e2e_viewer");
        await page.goto("/accounting/trades", { waitUntil: "networkidle" });
        await chooseEntity(page, "E2E Mercantile LLP");
        const row = page.getByRole("row").filter({ hasText: "E2E/COM/0001" });
        await expect(row.getByText("NOT ACCOUNTED")).toBeVisible();
        await expect(row.getByRole("button", { name: "Post to books" })).toHaveCount(0);
        await page.goto("/accounting/payments", { waitUntil: "networkidle" });
        await expect(page.getByRole("note")).toContainText("approver");
        await page.goto("/accounting/vouchers", { waitUntil: "networkidle" });
        await expect(page.getByRole("link", { name: "New journal" })).toHaveCount(0);
        await page.goto("/accounting/reports/trial-balance", { waitUntil: "networkidle" });
        await expect(page.getByText("MATCHED").first()).toBeVisible();  // reading still works

        await signIn(page, "e2e_trade_only");
        const nav = page.getByRole("navigation", { name: "Main navigation" });
        await expect(nav.getByRole("button", { name: "Accounting", exact: true })).toHaveCount(0);
        await page.goto("/accounting/dashboard", { waitUntil: "networkidle" });
        await expect(page).not.toHaveURL(/\/accounting\/dashboard/);
    });

    test("breadcrumbs, active menu highlighting and in-workspace navigation", async ({ page }) => {
        await signIn(page, "e2e_approver");
        await page.goto("/accounting/reports/cash-flow", { waitUntil: "networkidle" });
        const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
        await expect(crumbs.getByRole("link", { name: "Accounting" })).toBeVisible();
        await expect(crumbs.getByRole("link", { name: "Reports" })).toBeVisible();
        await expect(crumbs.getByText("Cash Flow")).toHaveAttribute("aria-current", "page");
        const nav = page.getByRole("navigation", { name: "Main navigation" });
        await expect(nav.getByRole("button", { name: "Accounting", exact: true })).toHaveClass(/is-active/);
        await expect(page.getByRole("navigation", { name: "Accounting sections" }).getByRole("link", { name: "Reports" }))
            .toHaveAttribute("aria-current", "page");
        await crumbs.getByRole("link", { name: "Accounting" }).click();
        await expect(page).toHaveURL(/\/accounting\/dashboard$/);
        // Existing Trade and Licence navigation is untouched.
        await nav.getByRole("button", { name: "Operations", exact: true }).hover();
        await expect(page.getByRole("menuitem", { name: "Trade In & Out" })).toBeVisible();
    });

    for (const vp of [{ name: "desktop", width: 1440, height: 900 }, { name: "tablet", width: 768, height: 1024 },
        { name: "mobile", width: 390, height: 844 }]) {
        test(`major screens fit the ${vp.name} viewport without horizontal overflow`, async ({ page }) => {
            await page.setViewportSize({ width: vp.width, height: vp.height });
            await signIn(page, "e2e_approver");
            await page.goto("/accounting/dashboard", { waitUntil: "networkidle" });
            await chooseEntity(page, "E2E Mercantile LLP");  // the entity with posted data (choice persists)
            for (const route of ["dashboard", "trades", "payments", "banking/workbench", "reports/trial-balance",
                "reports/profit-loss", "reports/balance-sheet", "vouchers"]) {
                await page.goto(`/accounting/${route}`, { waitUntil: "networkidle" });
                await expect(page.getByRole("combobox", { name: "Entity" })).toBeVisible();
                await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
                    { message: `${route} overflows at ${vp.width}px` }).toBeTruthy();
                if (process.env.LM_E2E_SCREENSHOTS) {
                    await page.screenshot({ path: `${process.env.LM_E2E_SCREENSHOTS}/${vp.name}-${route.replace(/\//g, "-")}.png` });
                }
            }
            if (vp.name === "mobile") {
                await page.getByRole("button", { name: "Open navigation menu" }).click();
                await expect(page.getByRole("region", { name: "Accounting" }).or(page.locator('section[aria-label="Accounting"]'))).toBeVisible();
            }
        });
    }
});
