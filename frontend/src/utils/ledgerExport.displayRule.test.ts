/**
 * ledgerExport — ledger transaction DISPLAY RULE + financial-safety suite.
 *
 * Two invariants are locked down here:
 *   1. Only the rows the display rule prescribes are PRINTED.
 *   2. Every total keeps reading the FULL financial collection — a suppressed
 *      opening row must not move a single exported figure.
 */

import autoTable from "jspdf-autotable";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { generatePDF } from "./ledgerExport";
import { formatIndianNumber } from "./numberFormatter";

// ─── jsPDF / autoTable capture harness ──────────────────────────────────────

const fakeDoc = {
    internal: { pageSize: { getWidth: () => 297, getHeight: () => 210 } },
    lastAutoTable: { finalY: 100 },
    addPage: vi.fn(),
    setFontSize: vi.fn(),
    setFont: vi.fn(),
    setTextColor: vi.fn(),
    setDrawColor: vi.fn(),
    setLineWidth: vi.fn(),
    text: vi.fn(),
    line: vi.fn(),
    link: vi.fn(),
    save: vi.fn(),
};

vi.mock("jspdf", () => ({ jsPDF: vi.fn(() => fakeDoc) }));
vi.mock("jspdf-autotable", () => ({ default: vi.fn() }));

const mockedAutoTable = vi.mocked(autoTable);

type PdfCell = string | { content?: unknown; colSpan?: number };
type PdfRow = PdfCell[];

/** autoTable call 0 = summary page, call 1 = the licence's detail page. */
function bodyOf(callIndex: number): PdfRow[] {
    const options = mockedAutoTable.mock.calls[callIndex]?.[1] as { body?: PdfRow[] } | undefined;
    return options?.body ?? [];
}

/** Full-width single-cell rows are the company section headers. */
function sectionHeaders(body: PdfRow[]): string[] {
    return body
        .filter((row) => row.length === 1 && typeof row[0] === "object")
        .map((row) => String((row[0] as { content?: unknown }).content ?? ""));
}

/** Plain string arrays are the printed transaction rows. */
function transactionRows(body: PdfRow[]): string[][] {
    return body.filter((row) => row.every((cell) => typeof cell === "string")) as string[][];
}

/** Rows of `{content}` objects are the per-company total rows. */
function totalRows(body: PdfRow[]): string[][] {
    return body
        .filter((row) => row.length > 1 && row.every((cell) => typeof cell === "object"))
        .map((row) => row.map((cell) => String((cell as { content?: unknown }).content ?? "")));
}

// ─── Fixtures — canonical ledger responses, as the screen passes them ───────

const OPENING = {
    date: "2026-01-01", id: 1, type: "OPENING",
    company_id: null, company_name: null,
    amount: "65380.63", is_commission: false, affects_balance: true,
    license_running_balance: "65380.63", company_utilization_after: null,
    display_status: "Opening Balance",
};
const PURCHASE = {
    date: "2026-02-01", id: 2, type: "PURCHASE",
    company_id: 7, company_name: "Acme Exports",
    amount: "65380.63", is_commission: false, affects_balance: true,
    license_running_balance: "65380.63", company_utilization_after: "65380.63",
    display_status: "",
};
const SALE = {
    date: "2026-03-01", id: 3, type: "SALE",
    company_id: 8, company_name: "Beta Traders",
    amount: "20000.00", is_commission: false, affects_balance: true,
    license_running_balance: "45380.63", company_utilization_after: "-20000.00",
    display_status: "",
};

function buildLedger(transactions: Record<string, unknown>[]) {
    return {
        license_id: 1,
        license_number: "LIC/1",
        license_type: "DFIA",
        license_date: "2026-01-01",
        expiry_date: "2027-01-01",
        exporter_name: "Exporter Ltd",
        opening_balance: "65380.63",
        license_running_balance: "45380.63",
        closing_balance: "45380.63",
        transactions,
        company_utilizations: {},
        totals: { total_purchases: "65380.63", total_sales: "20000.00", total_commission: "0.00" },
    };
}

beforeEach(() => {
    vi.clearAllMocks();
    fakeDoc.lastAutoTable = { finalY: 100 };
});

// ─── (i) Which rows get printed ─────────────────────────────────────────────

describe("generatePDF — ledger display rule (rows)", () => {
    it("prints no opening row and no bogus N/A section once a purchase exists", () => {
        generatePDF([buildLedger([OPENING, PURCHASE, SALE])], "test.pdf");

        const detail = bodyOf(1);
        expect(sectionHeaders(detail)).toEqual(["Acme Exports", "Beta Traders"]);
        expect(sectionHeaders(detail)).not.toContain("N/A");
        // One printed row per company: the purchase and the sale, nothing else.
        expect(transactionRows(detail)).toHaveLength(2);
    });

    it("still prints the opening row as the starting state when no purchase exists", () => {
        generatePDF([buildLedger([OPENING, SALE])], "test.pdf");

        const detail = bodyOf(1);
        // Company-keyed groups sort ahead of the company-less opening group
        // (pre-existing `groupByCompany` key ordering — unchanged by this fix).
        expect(sectionHeaders(detail)).toEqual(["Beta Traders", "N/A"]);
        expect(transactionRows(detail)).toHaveLength(2);
    });

    it("prints the opening row alone when it is the only transaction", () => {
        generatePDF([buildLedger([OPENING])], "test.pdf");

        const detail = bodyOf(1);
        expect(sectionHeaders(detail)).toEqual(["N/A"]);
        expect(transactionRows(detail)).toHaveLength(1);
    });

    it("preserves chronological/company order of the printed sections", () => {
        generatePDF([buildLedger([OPENING, PURCHASE, SALE])], "test.pdf");
        expect(sectionHeaders(bodyOf(1))).toEqual(["Acme Exports", "Beta Traders"]);
    });
});

// ─── (ii) FINANCIAL SAFETY — totals must not move ───────────────────────────

describe("generatePDF — financial safety (totals read the full collection)", () => {
    it("keeps every per-company total identical whether or not an opening row exists", () => {
        generatePDF([buildLedger([OPENING, PURCHASE, SALE])], "with-opening.pdf");
        const withOpening = totalRows(bodyOf(1));

        vi.clearAllMocks();
        generatePDF([buildLedger([PURCHASE, SALE])], "without-opening.pdf");
        const withoutOpening = totalRows(bodyOf(1));

        expect(withOpening).toEqual(withoutOpening);
    });

    it("reports the purchase company's debit/credit/balance from the full collection", () => {
        generatePDF([buildLedger([OPENING, PURCHASE, SALE])], "test.pdf");

        const [acmeTotal, betaTotal] = totalRows(bodyOf(1));
        expect(acmeTotal[0]).toBe("Total — Acme Exports");
        expect(acmeTotal[1]).toBe(formatIndianNumber(65380.63, 2));   // debit
        expect(acmeTotal[2]).toBe("-");                                // credit
        expect(acmeTotal[3]).toBe(formatIndianNumber(65380.63, 2));   // balance

        expect(betaTotal[0]).toBe("Total — Beta Traders");
        expect(betaTotal[1]).toBe("-");
        expect(betaTotal[2]).toBe(formatIndianNumber(20000, 2));
        expect(betaTotal[3]).toBe(formatIndianNumber(45380.63, 2));
    });

    it("leaves the summary page — a totals-only surface — completely unfiltered", () => {
        generatePDF([buildLedger([OPENING, PURCHASE, SALE])], "test.pdf");

        const summary = bodyOf(0);
        // The opening row's company-less group is deliberately still summarised
        // there, because its aggregate is what that page is made of.
        expect(sectionHeaders(summary)).toEqual(["Acme Exports", "Beta Traders", "N/A"]);
    });
});
