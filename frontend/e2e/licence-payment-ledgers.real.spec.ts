import { expect, test, type Browser, type Page } from "@playwright/test";

/**
 * REAL BACKEND — Purchase / Sale / Bank Payment ledgers inside the expanded licence on the one-page Licence Ledger.
 *
 * Opt-in: `LM_E2E_SEED=seed_payment_ledger_e2e scripts/test/run_data_bearing_browser_e2e.sh e2e/licence-payment-ledgers.real.spec.ts`
 * (fresh `test_*` database; licence 3411008090 / id 2509: purchase half paid + settled + bank-matched,
 * sale fully received with an unreconciled receipt; users e2e_ledger_accounts / e2e_ledger_trade).
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1" && process.env.LM_E2E_SEED === "seed_payment_ledger_e2e";
const LICENCE = "3411008090";
const LICENCE_ID = 2509;
const SEED_PASSWORD = "e2e-Ledger-2026!";

type Num = string | number;
interface TradeLedger { summary: { invoice_count: number; total_amount: Num; total_settled: Num; total_outstanding: Num }; rows: { invoice_number: string; total: Num; settled: Num; outstanding: Num; status: string }[] }
interface BankLedger { summary: { transaction_count: number; total_payments: Num; total_receipts: Num; total_allocated: Num; total_unallocated: Num }; rows: { payment_id: number; reference: string; reconciliation: string; allocated_to_licence: Num; unallocated: Num }[] }

async function signIn(page: Page, username = process.env.LM_USERNAME || "hardik", password = process.env.LM_PASSWORD || "admin@123") {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(username);
    await page.locator("#login-password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function apiGet<T>(page: Page, path: string): Promise<{ status: number; body: T }> {
    return page.evaluate(async url => {
        const r = await fetch(`/api/${url}`, { headers: { Authorization: `Bearer ${localStorage.getItem("access")}` } });
        return { status: r.status, body: await r.json().catch(() => ({})) };
    }, path) as Promise<{ status: number; body: T }>;
}

const inr = (v: Num) => Math.abs(Number(v)).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sum = (values: Num[]) => values.reduce<number>((t, v) => t + Number(v), 0);

/** Opens licence 2509's inline workspace from the one-page ledger and returns it. */
async function openLicence(page: Page) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/license-ledger", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: LICENCE, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/license-ledger/${LICENCE_ID}/\\d+$`));
    const workspace = page.getByRole("region", { name: `Licence ${LICENCE} workspace` });
    await expect(workspace).toBeVisible();
    return workspace;
}

async function newSession(browser: Browser, username: string): Promise<Page> {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();
    await signIn(page, username, SEED_PASSWORD);
    return page;
}

test.describe("Licence payment ledgers (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated browser harness with LM_E2E_SEED=seed_payment_ledger_e2e.");
    test.describe.configure({ mode: "serial" });

    test("purchase, sale and bank ledgers show linked records once, with totals that reconcile with the backend", async ({ page }, testInfo) => {
        await signIn(page);
        const workspace = await openLicence(page);
        const trade = (await apiGet<{ purchase: TradeLedger; sale: TradeLedger }>(page, `licenses/${LICENCE_ID}/overview-payment-ledgers/`)).body;
        const bank = await apiGet<BankLedger>(page, `accounting/licence-bank-ledger/${LICENCE_ID}/`);
        expect(bank.status).toBe(200);

        // Backend totals reconcile with its own rows.
        for (const ledger of [trade.purchase, trade.sale]) {
            expect(ledger.summary.invoice_count).toBe(ledger.rows.length);
            expect(sum(ledger.rows.map(r => r.total))).toBeCloseTo(Number(ledger.summary.total_amount), 2);
            expect(sum(ledger.rows.map(r => r.settled))).toBeCloseTo(Number(ledger.summary.total_settled), 2);
            expect(sum(ledger.rows.map(r => r.outstanding))).toBeCloseTo(Number(ledger.summary.total_outstanding), 2);
        }
        expect(trade.purchase.rows.map(r => r.status)).toEqual(["PARTIAL"]);
        expect(trade.sale.rows.map(r => r.status)).toEqual(["PAID"]);
        // One row per bank transaction, never duplicated.
        expect(bank.body.rows).toHaveLength(2);
        expect(new Set(bank.body.rows.map(r => r.payment_id)).size).toBe(2);
        expect(bank.body.summary.transaction_count).toBe(2);
        expect(sum(bank.body.rows.map(r => r.allocated_to_licence))).toBeCloseTo(Number(bank.body.summary.total_allocated), 2);
        expect(sum(bank.body.rows.map(r => r.unallocated))).toBeCloseTo(Number(bank.body.summary.total_unallocated), 2);
        // Both bank items are fully linked to this licence (settlement / trade receipt): nothing left unallocated,
        // and the receipt (no bill-wise settlement) is still traceable to the sale invoice.
        expect(Number(bank.body.summary.total_unallocated)).toBe(0);
        const saleNo = trade.sale.rows[0].invoice_number;
        const receipt = (bank.body.rows as unknown as { reference: string; invoices: { number: string }[] }[]).find(r => r.reference === "E2E-UTR-SAL-2509")!;
        expect(receipt.invoices.map(i => i.number)).toEqual([saleNo]);

        // Purchase Ledger tab (inline): summary = backend totals, Partially paid, allocation with its bank reference.
        await workspace.getByRole("tab", { name: "Purchase Ledger" }).click();
        const purchaseSummary = workspace.getByLabel("Purchase ledger summary");
        await expect(purchaseSummary).toContainText(inr(trade.purchase.summary.total_amount));
        await expect(purchaseSummary).toContainText(inr(trade.purchase.summary.total_settled));
        await expect(purchaseSummary).toContainText(inr(trade.purchase.summary.total_outstanding));
        const purchaseTable = workspace.getByRole("table", { name: "Purchase ledger" });
        await expect(purchaseTable.locator("[data-slot=badge]", { hasText: "Partially paid" })).toBeVisible();
        const purchaseNo = trade.purchase.rows[0].invoice_number;
        await workspace.getByRole("button", { name: `Show payments for invoice ${purchaseNo}` }).click();
        const allocations = workspace.getByRole("table", { name: `Payments for invoice ${purchaseNo}` });
        await expect(allocations).toContainText("E2E part payment");
        await expect(allocations).toContainText("E2E-UTR-PUR-2509");
        await page.screenshot({ path: testInfo.outputPath("purchase-ledger-1440.png"), fullPage: true });

        // Sale Ledger tab: Paid.
        await workspace.getByRole("tab", { name: "Sale Ledger" }).click();
        await expect(workspace.getByLabel("Sale ledger summary")).toContainText(inr(trade.sale.summary.total_settled));
        await expect(workspace.getByRole("table", { name: "Sale ledger" }).locator("[data-slot=badge]", { hasText: /^Paid$/ })).toBeVisible();

        // Bank Payment Ledger tab: two rows (payment + receipt), reconciliation, allocations traceable to invoices.
        await workspace.getByRole("tab", { name: "Bank Payment Ledger" }).click();
        const bankTable = workspace.getByRole("table", { name: "Bank payment ledger" });
        await expect(bankTable.getByRole("button", { name: /^Show allocations for / })).toHaveCount(2);
        await expect(bankTable.locator("[data-slot=badge]", { hasText: /^Reconciled$/ })).toBeVisible();
        await expect(bankTable.locator("[data-slot=badge]", { hasText: /^Unreconciled$/ })).toBeVisible();
        await expect(workspace.getByLabel("Bank payment ledger summary")).toContainText(inr(bank.body.summary.total_allocated));
        await workspace.getByRole("button", { name: "Show allocations for E2E-UTR-PUR-2509" }).click();
        await expect(workspace.getByRole("table", { name: "Invoice allocations for E2E-UTR-PUR-2509" })).toContainText(purchaseNo);
        await expect(workspace.getByRole("table", { name: "Statement lines for E2E-UTR-PUR-2509" })).toContainText("E2E-UTR-PUR-2509");
        await expect(bankTable.getByRole("row").filter({ hasText: "E2E-UTR-SAL-2509" })).toContainText(trade.sale.rows[0].invoice_number);
        await page.screenshot({ path: testInfo.outputPath("bank-ledger-1440.png"), fullPage: true });

        // Existing Invoices tab still works; nothing navigated away.
        await workspace.getByRole("tab", { name: "Invoices" }).click();
        await expect(workspace.getByRole("tabpanel")).toContainText(purchaseNo);
        await expect(page.getByRole("heading", { level: 1 })).toHaveText("License Ledger");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("Ledger tab: licence header, financial cards, company-wise transactions with bank payment/receipt details", async ({ page }, testInfo) => {
        await signIn(page);
        const workspace = await openLicence(page);
        const bank = (await apiGet<{ summary: Record<string, Num>; trades: { invoice_number: string; direction: string; status: string; bank_settled: Num; outstanding: Num }[] }>(page, `accounting/licence-bank-ledger/${LICENCE_ID}/`)).body;
        const purchase = bank.trades.find(t => t.direction === "PURCHASE")!;
        const sale = bank.trades.find(t => t.direction === "SALE")!;
        expect([purchase.status, sale.status]).toEqual(["PARTIAL", "PAID"]);

        await workspace.getByRole("tab", { name: "Ledger", exact: true }).click();
        const panel = workspace.getByRole("tabpanel");
        // A — licence header and B — the four financial cards (existing trusted figures).
        await expect(panel.getByText(LICENCE).first()).toBeVisible();
        for (const card of ["TOTAL PURCHASE", "TOTAL SALE", "CURRENT BALANCE"]) await expect(panel.getByText(card, { exact: false }).first()).toBeVisible();
        // Bank movement summary: licence-linked, equal to the backend summary.
        const summary = panel.getByRole("region", { name: "Bank movement summary" });
        await expect(summary).toContainText("licence-linked only");
        await expect(summary).toContainText(inr(bank.summary.total_withdrawals));
        await expect(summary).toContainText(inr(bank.summary.total_credits));
        await expect(summary).toContainText(inr(bank.summary.total_outstanding_purchase));
        // C — company-wise table with a Bank column; purchase partially paid via a bank withdrawal.
        const purchaseToggle = panel.getByRole("button", { name: `Bank details for invoice ${purchase.invoice_number}` });
        await expect(purchaseToggle).toContainText("Partially paid");
        await purchaseToggle.click();
        const pDetails = panel.getByRole("region", { name: `Bank details for invoice ${purchase.invoice_number}` });
        const pTable = pDetails.getByRole("table", { name: `Bank transactions for invoice ${purchase.invoice_number}` });
        await expect(pTable).toContainText("E2E-UTR-PUR-2509");
        await expect(pTable).toContainText("WITHDRAWAL / DEBIT");
        await expect(pTable).toContainText("Reconciled");
        await expect(pDetails).toContainText(`Outstanding ${"₹" + inr(purchase.outstanding)}`);
        await page.screenshot({ path: testInfo.outputPath("ledger-tab-bank-1440.png"), fullPage: true });
        // Sale fully received via a bank credit (unreconciled).
        const saleToggle = panel.getByRole("button", { name: `Bank details for invoice ${sale.invoice_number}` });
        await expect(saleToggle).toContainText("Received");
        await saleToggle.click();
        const sTable = panel.getByRole("table", { name: `Bank transactions for invoice ${sale.invoice_number}` });
        await expect(sTable).toContainText("DEPOSIT / CREDIT");
        await expect(sTable).toContainText("Unreconciled");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("permissions: trade-only user sees purchase/sale ledgers but no bank ledger (API 403); accounts viewer sees bank", async ({ browser }) => {
        const tradeOnly = await newSession(browser, "e2e_ledger_trade");
        try {
            const workspace = await openLicence(tradeOnly);
            await expect(workspace.getByRole("tab", { name: "Purchase Ledger" })).toBeVisible();
            await expect(workspace.getByRole("tab", { name: "Sale Ledger" })).toBeVisible();
            await expect(workspace.getByRole("tab", { name: "Bank Payment Ledger" })).toHaveCount(0);
            await workspace.getByRole("tab", { name: "Ledger", exact: true }).click();
            await expect(workspace.getByText("Bank payment and receipt details are shown to accounting roles.")).toBeVisible();
            await expect(workspace.getByRole("button", { name: /^Bank details for invoice/ })).toHaveCount(0);
            expect((await apiGet(tradeOnly, `accounting/licence-bank-ledger/${LICENCE_ID}/`)).status).toBe(403);
            expect((await apiGet(tradeOnly, `licenses/${LICENCE_ID}/overview-payment-ledgers/`)).status).toBe(200);
        } finally {
            await tradeOnly.context().close();
        }

        const accounts = await newSession(browser, "e2e_ledger_accounts");
        try {
            const workspace = await openLicence(accounts);
            await workspace.getByRole("tab", { name: "Bank Payment Ledger" }).click();
            await expect(workspace.getByRole("table", { name: "Bank payment ledger" }).getByRole("button", { name: /^Show allocations for / })).toHaveCount(2);
        } finally {
            await accounts.context().close();
        }
    });
});
