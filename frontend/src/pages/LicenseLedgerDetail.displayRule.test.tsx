/**
 * LicenseLedgerDetail — ledger transaction DISPLAY RULE regression suite.
 *
 * Screenshot bug being locked down: a licence that HAS a PURCHASE also rendered
 * a separate company group titled "N/A" holding the synthetic OPENING row (the
 * same figure as the purchase, double-presented), because the opening row's
 * `company_id` is null and so formed its own group.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import type { CanonicalLedgerResponse, CanonicalTransaction } from "../types/canonicalLedger";
import { selectLedgerDisplayRows } from "@/utils/ledgerDisplayRows";
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

const OPENING: CanonicalTransaction = {
    date: "2026-01-01", id: 1, type: "OPENING",
    company_id: null, company_name: null,
    amount: "65380.63", is_commission: false, affects_balance: true,
    license_running_balance: "65380.63", company_utilization_after: null,
    display_status: "Opening Balance",
};
const PURCHASE: CanonicalTransaction = {
    date: "2026-02-01", id: 2, type: "PURCHASE",
    company_id: 7, company_name: "Acme Exports",
    amount: "65380.63", is_commission: false, affects_balance: true,
    license_running_balance: "65380.63", company_utilization_after: "65380.63",
    display_status: "",
};
const SALE: CanonicalTransaction = {
    date: "2026-03-01", id: 3, type: "SALE",
    company_id: 8, company_name: "Beta Traders",
    amount: "20000.00", is_commission: false, affects_balance: true,
    license_running_balance: "45380.63", company_utilization_after: "-20000.00",
    display_status: "",
};

interface MatrixCase {
    label: string;
    purchase: boolean;
    sale: boolean;
    opening: boolean;
    transactions: CanonicalTransaction[];
}

/** Same five cases as the selector matrix, exercised through the real screen. */
const MATRIX: MatrixCase[] = [
    { label: "PURCHASE + SALE + OPENING", purchase: true, sale: true, opening: true, transactions: [OPENING, PURCHASE, SALE] },
    { label: "PURCHASE + OPENING", purchase: true, sale: false, opening: true, transactions: [OPENING, PURCHASE] },
    { label: "SALE + OPENING (no purchase)", purchase: false, sale: true, opening: true, transactions: [OPENING, SALE] },
    { label: "OPENING only", purchase: false, sale: false, opening: true, transactions: [OPENING] },
    { label: "no transactions at all", purchase: false, sale: false, opening: false, transactions: [] },
];

/** Build the response exactly as the canonical API serves it. */
function buildResponse(transactions: CanonicalTransaction[]): CanonicalLedgerResponse {
    const { rows, openingRow } = selectLedgerDisplayRows<CanonicalTransaction>({ transactions });
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
        opening_balance: "65380.63",
        license_running_balance: "45380.63",
        closing_balance: "45380.63",
        transactions,
        display_transactions: rows,
        opening_display: openingRow,
        company_utilizations: {
            "7": { company_id: 7, company_name: "Acme Exports", utilization_balance: "65380.63" },
            "8": { company_id: 8, company_name: "Beta Traders", utilization_balance: "-20000.00" },
        },
        totals: { total_purchases: "65380.63", total_sales: "20000.00", total_commission: "0.00" },
    };
}

async function renderLedger(transactions: CanonicalTransaction[]) {
    mockedApiGet.mockResolvedValue({ data: buildResponse(transactions) });
    render(<LicenseLedgerDetail />);
    await waitFor(() => expect(mockedApiGet).toHaveBeenCalled());
    // The header always renders once loading resolves.
    await screen.findByText("Exporter Ltd");
}

beforeEach(() => {
    vi.clearAllMocks();
});

// ─── Scoped queries ─────────────────────────────────────────────────────────
// "N/A" also legitimately appears in the licence header (SION Norms), and
// company names also appear in each row's Particulars cell — so every
// grouping assertion is scoped to the company-group headings themselves.

const companyGroupNames = (): string[] =>
    screen.queryAllByTestId("ledger-company-group").map((el) => el.textContent?.trim() ?? "");

const companyBlocks = (): HTMLElement[] => screen.queryAllByTestId("ledger-company-block");

const openingState = (): HTMLElement | null => screen.queryByTestId("ledger-opening-state");

// ─── The matrix, through the real screen ────────────────────────────────────

describe.each(MATRIX)("LicenseLedgerDetail display rule — $label", (testCase) => {
    it("renders the opening balance as a starting state only when no purchase exists", async () => {
        await renderLedger(testCase.transactions);

        expect(Boolean(openingState())).toBe(testCase.opening && !testCase.purchase);

        // The OPENING badge must never appear inside a company group.
        for (const block of companyBlocks()) {
            expect(within(block).queryByText("OPENING")).toBeNull();
        }
    });

    it("renders sale rows regardless of whether a purchase exists", async () => {
        await renderLedger(testCase.transactions);
        expect(screen.queryAllByText("SALE").length > 0).toBe(testCase.sale);
    });

    it("renders purchase rows when present", async () => {
        await renderLedger(testCase.transactions);
        expect(screen.queryAllByText("PURCHASE").length > 0).toBe(testCase.purchase);
    });

    it("shows the empty state only when there is nothing to display", async () => {
        await renderLedger(testCase.transactions);
        const isEmpty = !testCase.purchase && !testCase.sale && !testCase.opening;
        expect(Boolean(screen.queryByText("No transactions"))).toBe(isEmpty);
    });

    it("emits no duplicate transaction rows", async () => {
        await renderLedger(testCase.transactions);
        // One type badge per rendered row; OPENING sits outside the groups.
        expect(screen.queryAllByText("PURCHASE")).toHaveLength(testCase.purchase ? 1 : 0);
        expect(screen.queryAllByText("SALE")).toHaveLength(testCase.sale ? 1 : 0);
        expect(screen.queryAllByText("OPENING")).toHaveLength(
            testCase.opening && !testCase.purchase ? 1 : 0,
        );
    });

    it('never produces a bogus "N/A" company group', async () => {
        await renderLedger(testCase.transactions);
        // The company-less OPENING row is excluded from grouping, so the
        // "N/A" fallback name in `groupTransactionsByCompany` is unreachable.
        expect(companyGroupNames()).not.toContain("N/A");
        // Exactly the companies that own a rendered row, nothing else.
        const expectedGroups = [
            ...(testCase.purchase ? ["Acme Exports"] : []),
            ...(testCase.sale ? ["Beta Traders"] : []),
        ];
        expect(companyGroupNames()).toEqual(expectedGroups);
    });
});

// ─── The screenshot regression, explicitly ──────────────────────────────────

describe("LicenseLedgerDetail — screenshot regression", () => {
    it("does not double-present the opening balance as an N/A company group", async () => {
        await renderLedger([OPENING, PURCHASE]);

        expect(companyGroupNames()).toEqual(["Acme Exports"]);
        expect(openingState()).toBeNull();
        expect(screen.queryAllByText("OPENING")).toHaveLength(0);

        // The $65,380.63 figure is presented as a single ledger row (the
        // purchase), not twice (purchase row + phantom opening row).
        const matchingCells = companyBlocks().flatMap((block) =>
            Array.from(block.querySelectorAll("tbody td")).filter(
                (cell) => cell.textContent === "$65,380.63",
            ),
        );
        expect(matchingCells).toHaveLength(1);
    });

    it("keeps the opening balance as a starting state when no purchase exists", async () => {
        await renderLedger([OPENING, SALE]);

        const opening = openingState();
        expect(opening).not.toBeNull();
        expect(within(opening as HTMLElement).getByText("OPENING")).toBeTruthy();
        expect(
            within(opening as HTMLElement).getByText(/carried forward, not a transaction/),
        ).toBeTruthy();
        // ...and it is NOT one of the company groups.
        expect(companyGroupNames()).toEqual(["Beta Traders"]);
        expect(screen.getAllByText("SALE")).toHaveLength(1);
    });

    it("preserves chronological order of the rendered rows", async () => {
        await renderLedger([OPENING, PURCHASE, SALE]);
        expect(companyGroupNames()).toEqual(["Acme Exports", "Beta Traders"]);
    });

    it("falls back to the compatibility shim for payloads without the new fields", async () => {
        const legacy = buildResponse([OPENING, PURCHASE]) as unknown as Record<string, unknown>;
        delete legacy.display_transactions;
        delete legacy.opening_display;
        mockedApiGet.mockResolvedValue({ data: legacy });

        render(<LicenseLedgerDetail />);
        await screen.findByText("Exporter Ltd");

        expect(companyGroupNames()).toEqual(["Acme Exports"]);
        expect(openingState()).toBeNull();
        expect(screen.queryAllByText("OPENING")).toHaveLength(0);
        expect(screen.getAllByText("PURCHASE")).toHaveLength(1);
    });
});
