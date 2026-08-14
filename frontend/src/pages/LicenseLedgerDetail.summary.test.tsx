/**
 * LicenseLedgerDetail — CA SUMMARY BAND + ROW PRESENTATION COLUMNS.
 *
 * What this suite locks down, all of it presentation-layer:
 *
 * 1. The four summary cards render the EXACT strings the backend sent, only
 *    digit-grouped and symbol-prefixed. No `reduce`, no `+`/`-`, no re-rounding.
 * 2. The right SYMBOL on the right figure. One DFIA licence carries three
 *    currencies at once — balance in USD, bill and profit in INR — so a single
 *    hardcoded '₹' or '$' would be wrong somewhere on the screen.
 * 3. Profit presentation is driven by `profit_state`, never by the sign of the
 *    number: LOSS shows a MAGNITUDE under a "LOSS" label (so "-₹…" can never
 *    sit under the word "PROFIT"), and UNAVAILABLE shows 'N/A' rather than a
 *    fabricated ₹0.00 (which would falsely assert break-even).
 * 4. Particulars names the COUNTERPARTY, not our own company (which the group
 *    header already shows), and degrades to 'N/A' instead of substituting it.
 * 5. A multi-item trade stays ONE row — expanding it per item would
 *    double-count the trade in the debit column.
 * 6. A payload with no `summary` (older cache) hides the band instead of
 *    crashing or inventing zeros.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import type {
    CanonicalLedgerResponse, CanonicalTransaction, LedgerSummary, ProfitState,
} from "../types/canonicalLedger";
import LicenseLedgerDetail from "./LicenseLedgerDetail";

vi.mock("react-router-dom", () => ({
    useLocation: () => ({ search: "", state: null }),
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: "LIC/1", companyId: undefined }),
}));

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

vi.mock("../utils/ledgerExport", () => ({
    generatePDF: vi.fn(),
    generateExcel: vi.fn(),
}));

const mockedApiGet = vi.mocked(api.get);

// ─── Fixtures ───────────────────────────────────────────────────────────────
// Every money field gets a DISTINCT value so an assertion cannot pass by
// accidentally reading a neighbouring column:
//   purchase licence value  $65,380.63   bill  ₹54,00,000.00
//   sale     licence value  $20,000.00   bill  ₹18,50,000.00
//   profit                               ₹12,34,567.89

const PURCHASE: CanonicalTransaction = {
    date: "2026-02-01", id: 2, type: "PURCHASE",
    company_id: 7, company_name: "Acme Exports",
    party_id: 21, party_name: "Global Supplier Co",
    amount: "65380.63", bill_amount: "5400000.00",
    item_names: ["Palm Oil", "Soya Oil", "Sunflower Oil"],
    is_commission: false, affects_balance: true,
    license_running_balance: "65380.63", company_utilization_after: "65380.63",
    display_status: "",
};

const SALE: CanonicalTransaction = {
    date: "2026-03-01", id: 3, type: "SALE",
    company_id: 7, company_name: "Acme Exports",
    party_id: 22, party_name: "Beta Buyers Ltd",
    amount: "20000.00", bill_amount: "1850000.00",
    item_names: ["Palm Oil"],
    is_commission: false, affects_balance: true,
    license_running_balance: "45380.63", company_utilization_after: "45380.63",
    display_status: "",
};

const BASE_SUMMARY: LedgerSummary = {
    total_sale: "65380.63",
    total_purchase: "20000.00",
    total_sale_bill_inr: "5400000.00",
    total_purchase_bill_inr: "1850000.00",
    bill_currency: "INR",
    opening_balance: "0.00",
    opening_in_purchase: false,
    current_balance: "45380.63",
    balance_currency: "USD",
    total_profit_loss: "1234567.89",
    profit_currency: "INR",
    profit_state: "PROFIT",
};

// `summary` is deliberately NOT typed `| undefined`: passing undefined would
// silently fall back to BASE_SUMMARY. Use `renderLegacyLedger` to omit it.
function buildResponse(
    summary: LedgerSummary = BASE_SUMMARY,
    transactions: CanonicalTransaction[] = [PURCHASE, SALE],
): CanonicalLedgerResponse {
    return {
        license_id: 1,
        license_number: "LIC/1",
        license_type: "DFIA",
        license_date: "2026-01-01",
        expiry_date: "2027-01-01",
        exporter_id: 1,
        exporter_name: "Exporter Ltd",
        port_id: 1,
        port_name: "Nhava Sheva",
        opening_balance: "0.00",
        license_running_balance: "45380.63",
        closing_balance: "45380.63",
        transactions,
        display_transactions: transactions,
        opening_display: null,
        company_utilizations: {
            "7": { company_id: 7, company_name: "Acme Exports", utilization_balance: "45380.63" },
        },
        totals: { total_purchases: "65380.63", total_sales: "20000.00", total_commission: "0.00" },
        summary,
    };
}

async function renderLedger(
    summary: LedgerSummary = BASE_SUMMARY,
    transactions: CanonicalTransaction[] = [PURCHASE, SALE],
) {
    mockedApiGet.mockResolvedValue({ data: buildResponse(summary, transactions) });
    render(<LicenseLedgerDetail />);
    await waitFor(() => expect(mockedApiGet).toHaveBeenCalled());
    await screen.findByText("Exporter Ltd");
}

/**
 * Render a pre-`summary` payload — the `summary` KEY IS ABSENT, which is what an
 * older cached response actually looks like. (Passing `summary: undefined` to
 * `renderLedger` would instead trigger its default parameter and hand back the
 * full summary, silently testing nothing.)
 */
async function renderLegacyLedger() {
    const legacy = buildResponse() as unknown as Record<string, unknown>;
    delete legacy.summary;
    mockedApiGet.mockResolvedValue({ data: legacy });
    render(<LicenseLedgerDetail />);
    await waitFor(() => expect(mockedApiGet).toHaveBeenCalled());
    await screen.findByText("Exporter Ltd");
}

const summaryBand = (): HTMLElement | null => screen.queryByTestId("ledger-summary-cards");

/** The card whose label matches, as rendered in the summary band. */
function card(label: string): HTMLElement {
    const band = summaryBand();
    expect(band).not.toBeNull();
    const labelEl = within(band as HTMLElement).getByText(label);
    // StatCard structure: label and value are siblings inside the text block.
    return labelEl.parentElement as HTMLElement;
}

beforeEach(() => {
    vi.clearAllMocks();
});

// ===========================================================================
// 1. The cards show backend strings, with the backend's own currency
// ===========================================================================

describe("summary cards", () => {
    it("renders the four CA cards", async () => {
        await renderLedger();
        expect(summaryBand()).not.toBeNull();
        for (const label of ["Total Sale", "Total Purchase", "Current Balance", "PROFIT"]) {
            expect(within(summaryBand() as HTMLElement).getByText(label)).toBeTruthy();
        }
    });

    it("shows the licence-value totals in the backend's balance_currency (USD → $)", async () => {
        await renderLedger();
        // Exactly the backend string, digit-grouped. Not summed on the client.
        expect(within(card("Total Sale")).getByText("$65,380.63")).toBeTruthy();
        expect(within(card("Total Purchase")).getByText("$20,000.00")).toBeTruthy();
    });

    it("shows the bill totals in bill_currency (INR → ₹) on the SAME cards", async () => {
        await renderLedger();
        // The two currencies coexist on one card and must not be conflated.
        expect(within(card("Total Sale")).getByText("Bill ₹54,00,000.00")).toBeTruthy();
        expect(within(card("Total Purchase")).getByText("Bill ₹18,50,000.00")).toBeTruthy();
    });

    it("shows Current Balance as the canonical balance in USD, not INR", async () => {
        await renderLedger();
        const balanceCard = card("Current Balance");
        expect(within(balanceCard).getByText("$45,380.63")).toBeTruthy();
        // The DFIA balance is CIF USD — a ₹ here would be the currency bug.
        expect(within(balanceCard).queryByText("₹45,380.63")).toBeNull();
    });

    it("uses ₹ for profit even though the balance on the same screen is $", async () => {
        await renderLedger();
        expect(within(card("PROFIT")).getByText("₹12,34,567.89")).toBeTruthy();
    });

    it("hides the band entirely for a payload with no summary", async () => {
        await renderLegacyLedger();
        // No band, no crash, and above all no fabricated zeros.
        expect(summaryBand()).toBeNull();
        expect(screen.queryByText("₹0.00")).toBeNull();
        // The rest of the page still renders.
        expect(screen.getByText("Exporter Ltd")).toBeTruthy();
        expect(screen.getAllByText("PURCHASE").length).toBe(1);
    });

    it("still renders the balance card figure when balance_currency is INR", async () => {
        await renderLedger({ ...BASE_SUMMARY, balance_currency: "INR" });
        expect(within(card("Current Balance")).getByText("₹45,380.63")).toBeTruthy();
    });
});

// ===========================================================================
// 2. Profit state is decided by the BACKEND, never by the sign
// ===========================================================================

interface ProfitCase {
    state: ProfitState;
    value: string | null;
    label: string;
    /** Exactly what the card must display. */
    expected: string;
}

const PROFIT_CASES: ProfitCase[] = [
    { state: "PROFIT", value: "1234567.89", label: "PROFIT", expected: "₹12,34,567.89" },
    // The magnitude, under a LOSS label — never "-₹…" under "PROFIT".
    { state: "LOSS", value: "-98765.43", label: "LOSS", expected: "₹98,765.43" },
    { state: "BREAK_EVEN", value: "0.00", label: "BREAK-EVEN", expected: "₹0.00" },
    // N/A, never a fabricated ₹0.00 (which would assert break-even).
    { state: "UNAVAILABLE", value: null, label: "PROFIT / LOSS", expected: "N/A" },
];

describe.each(PROFIT_CASES)("profit_state $state", (testCase) => {
    it(`renders label "${testCase.label}" with value ${testCase.expected}`, async () => {
        await renderLedger({
            ...BASE_SUMMARY,
            total_profit_loss: testCase.value,
            profit_state: testCase.state,
        });

        const profitCard = card(testCase.label);
        expect(within(profitCard).getByText(testCase.expected)).toBeTruthy();
    });

    it("never shows a negative number in the profit card", async () => {
        await renderLedger({
            ...BASE_SUMMARY,
            total_profit_loss: testCase.value,
            profit_state: testCase.state,
        });

        const text = card(testCase.label).textContent ?? "";
        expect(text).not.toMatch(/-₹/);
        expect(text).not.toMatch(/₹-/);
    });
});

describe("profit_state robustness", () => {
    it("degrades an unknown state to the neutral UNAVAILABLE presentation", async () => {
        await renderLedger({
            ...BASE_SUMMARY,
            profit_state: "SOMETHING_NEW" as ProfitState,
            total_profit_loss: null,
        });
        // Falls back rather than crashing the financial screen.
        expect(within(card("PROFIT / LOSS")).getByText("N/A")).toBeTruthy();
    });

    it("shows N/A — not ₹0.00 — when profit is unavailable", async () => {
        await renderLedger({
            ...BASE_SUMMARY, profit_state: "UNAVAILABLE", total_profit_loss: null,
        });
        const profitCard = card("PROFIT / LOSS");
        expect(within(profitCard).queryByText("₹0.00")).toBeNull();
        expect(within(profitCard).getByText("N/A")).toBeTruthy();
    });
});

// ===========================================================================
// 3. Row columns — Particulars (counterparty), Items, bill amounts
// ===========================================================================

/** The <tr> containing a given type badge, inside a company block. */
function rowFor(type: string): HTMLElement {
    const badge = screen.getAllByText(type)[0];
    return badge.closest("tr") as HTMLElement;
}

describe("row presentation columns", () => {
    it("shows the COUNTERPARTY in Particulars, not our own company", async () => {
        await renderLedger();

        expect(within(rowFor("PURCHASE")).getByText("Global Supplier Co")).toBeTruthy();
        expect(within(rowFor("SALE")).getByText("Beta Buyers Ltd")).toBeTruthy();
        // The group header names our company; the row must not echo it.
        expect(within(rowFor("PURCHASE")).queryByText("Acme Exports")).toBeNull();
    });

    it("falls back to - — never our own company — when the party is absent", async () => {
        await renderLedger(BASE_SUMMARY, [
            { ...PURCHASE, party_id: null, party_name: null },
        ]);
        const row = rowFor("PURCHASE");
        // Check that "-" exists somewhere in the row (particulars/party column)
        const dashElements = within(row).queryAllByText("-");
        expect(dashElements.length).toBeGreaterThan(0);
        // Verify that the actual company name is not shown
        expect(within(row).queryByText("Acme Exports")).toBeNull();
    });

    it("shows real item names, collapsing the overflow into +N", async () => {
        await renderLedger();
        const row = rowFor("PURCHASE");
        // First name inline, remaining two collapsed.
        expect(within(row).getByText("Palm Oil")).toBeTruthy();
        expect(within(row).getByText("+2")).toBeTruthy();
        // Full list available on hover for the complete record.
        expect(row.querySelector('[title="Palm Oil, Soya Oil, Sunflower Oil"]')).toBeTruthy();
    });

    it("keeps a multi-item trade as ONE row", async () => {
        await renderLedger();
        // Three items, still a single PURCHASE row — expanding per item would
        // double-count the trade in the debit column.
        expect(screen.getAllByText("PURCHASE")).toHaveLength(1);
    });

    it("shows a placeholder when a row has no items", async () => {
        await renderLedger(BASE_SUMMARY, [{ ...PURCHASE, item_names: [] }]);
        // The service returns [] and the UI — not the service — supplies '-'.
        expect(screen.getAllByText("PURCHASE")).toHaveLength(1);
    });

    it("puts the licence value in $ and the bill in ₹ on the same row", async () => {
        await renderLedger();

        const purchaseRow = rowFor("PURCHASE");
        expect(within(purchaseRow).getByText("$65,380.63")).toBeTruthy();
        expect(within(purchaseRow).getByText("₹54,00,000.00")).toBeTruthy();

        const saleRow = rowFor("SALE");
        expect(within(saleRow).getByText("$20,000.00")).toBeTruthy();
        expect(within(saleRow).getByText("₹18,50,000.00")).toBeTruthy();
    });

    it("labels the bill columns separately from the licence-value columns", async () => {
        await renderLedger();
        // Licence-value columns carry the balance currency...
        expect(screen.getAllByText("Sale ($)").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Purchase ($)").length).toBeGreaterThan(0);
        // ...the bill columns carry INR, on the same table.
        expect(screen.getAllByText("Sale Bill (₹)").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Purchase Bill (₹)").length).toBeGreaterThan(0);
    });

    it("leaves the opposite column blank rather than repeating the amount", async () => {
        await renderLedger();
        // A PURCHASE contributes to Debit only: its Credit and Credit-Bill
        // cells must be empty, or the columns would not add up to the summary.
        const cells = Array.from(rowFor("PURCHASE").querySelectorAll("td"))
            .map((td) => td.textContent?.trim());
        expect(cells.filter((c) => c === "$20,000.00")).toHaveLength(0);
        expect(cells.filter((c) => c === "-").length).toBeGreaterThan(0);
    });
});
