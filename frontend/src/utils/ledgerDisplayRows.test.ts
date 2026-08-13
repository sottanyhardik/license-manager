import { describe, expect, it } from "vitest";

import {
    createDisplayRowFilter,
    DISPLAY_ROW_TYPES,
    isDisplayRow,
    isOpeningRow,
    isSaleRow,
    OPENING_ROW_TYPE,
    PURCHASE_PRESENCE_TYPES,
    selectDisplayRowsFromTransactions,
    selectLedgerDisplayRows,
} from "./ledgerDisplayRows";

// ─── Fixtures ───────────────────────────────────────────────────────────────
// Chronological, exactly as the canonical ledger service emits them
// (date ASC, id ASC). The synthetic OPENING row is company-less — that null
// `company_id` is what used to spawn the bogus "N/A" company group.

interface Row {
    id: number;
    type: string;
    date: string;
    company_id: number | null;
    company_name: string | null;
}

const OPENING: Row = { id: 1, type: "OPENING", date: "2026-01-01", company_id: null, company_name: null };
const PURCHASE: Row = { id: 2, type: "PURCHASE", date: "2026-02-01", company_id: 7, company_name: "Acme" };
const SALE_A: Row = { id: 3, type: "SALE", date: "2026-03-01", company_id: 8, company_name: "Beta" };
const SALE_B: Row = { id: 4, type: "SALE", date: "2026-04-01", company_id: 7, company_name: "Acme" };
const COMMISSION: Row = { id: 5, type: "COMMISSION", date: "2026-05-01", company_id: 7, company_name: "Acme" };

/**
 * THE RULE — one matrix, five cases, mirroring the backend table in
 * `transaction_semantics.py`.
 */
interface MatrixCase {
    label: string;
    purchase: boolean;
    sale: boolean;
    opening: boolean;
    transactions: Row[];
    expectedRows: Row[];
    expectedOpeningRow: Row | null;
}

const MATRIX: MatrixCase[] = [
    {
        label: "PURCHASE + SALE + OPENING → purchase and sale, no opening row",
        purchase: true, sale: true, opening: true,
        transactions: [OPENING, PURCHASE, SALE_A, SALE_B],
        expectedRows: [PURCHASE, SALE_A, SALE_B],
        expectedOpeningRow: null,
    },
    {
        label: "PURCHASE + OPENING → purchase only, no opening row",
        purchase: true, sale: false, opening: true,
        transactions: [OPENING, PURCHASE],
        expectedRows: [PURCHASE],
        expectedOpeningRow: null,
    },
    {
        label: "SALE + OPENING (no purchase) → opening as starting state, plus sale",
        purchase: false, sale: true, opening: true,
        transactions: [OPENING, SALE_A],
        expectedRows: [SALE_A],
        expectedOpeningRow: OPENING,
    },
    {
        label: "OPENING only → opening as starting state",
        purchase: false, sale: false, opening: true,
        transactions: [OPENING],
        expectedRows: [],
        expectedOpeningRow: OPENING,
    },
    {
        label: "nothing → empty state",
        purchase: false, sale: false, opening: false,
        transactions: [],
        expectedRows: [],
        expectedOpeningRow: null,
    },
];

/**
 * Both payload shapes must resolve identically:
 *  • canonical — the API already applied the rule server-side;
 *  • shim — an older or cached response that only carries `transactions`.
 */
const PAYLOAD_FLAVOURS: {
    label: string;
    build: (testCase: MatrixCase) => Record<string, unknown>;
}[] = [
    {
        label: "canonical payload (display_transactions / opening_display)",
        build: (testCase) => ({
            transactions: testCase.transactions,
            display_transactions: testCase.expectedRows,
            opening_display: testCase.expectedOpeningRow,
        }),
    },
    {
        label: "compatibility shim (transactions only)",
        build: (testCase) => ({ transactions: testCase.transactions }),
    },
];

// ─── Constants mirror the backend ───────────────────────────────────────────

describe("ledgerDisplayRows constants", () => {
    it("mirrors the backend transaction-type constants exactly", () => {
        expect(DISPLAY_ROW_TYPES).toEqual(["PURCHASE", "SALE"]);
        expect(OPENING_ROW_TYPE).toBe("OPENING");
        expect(PURCHASE_PRESENCE_TYPES).toEqual(["PURCHASE"]);
    });

    it("classifies individual rows without touching amounts", () => {
        expect(isDisplayRow(PURCHASE)).toBe(true);
        expect(isDisplayRow(SALE_A)).toBe(true);
        expect(isDisplayRow(OPENING)).toBe(false);
        expect(isDisplayRow(COMMISSION)).toBe(false);
        expect(isOpeningRow(OPENING)).toBe(true);
        expect(isOpeningRow(PURCHASE)).toBe(false);
        expect(isSaleRow(SALE_A)).toBe(true);
        expect(isSaleRow(PURCHASE)).toBe(false);
        // Defensive: malformed rows must not throw.
        expect(isDisplayRow(null)).toBe(false);
        expect(isDisplayRow({})).toBe(false);
        expect(isOpeningRow(undefined)).toBe(false);
    });
});

// ─── The matrix ─────────────────────────────────────────────────────────────

describe.each(PAYLOAD_FLAVOURS)("selectLedgerDisplayRows — $label", ({ build }) => {
    describe.each(MATRIX)("$label", (testCase) => {
        const payload = build(testCase);
        const selection = selectLedgerDisplayRows<Row>(payload);

        it("selects exactly the rows the rule prescribes", () => {
            expect(selection.rows).toEqual(testCase.expectedRows);
        });

        it("returns the opening row only as a separate starting state", () => {
            expect(selection.openingRow).toEqual(testCase.expectedOpeningRow);
            // Screenshot regression: an opening row is NEVER an ordinary row.
            expect(selection.rows.some(isOpeningRow)).toBe(false);
        });

        it("never renders the opening row when a purchase exists", () => {
            if (testCase.purchase) {
                expect(selection.openingRow).toBeNull();
            } else if (testCase.opening) {
                expect(selection.openingRow).not.toBeNull();
            }
        });

        it("renders sales regardless of whether a purchase exists", () => {
            const saleRows = selection.rows.filter(isSaleRow);
            expect(saleRows.length > 0).toBe(testCase.sale);
        });

        it("emits no duplicate rows", () => {
            const ids = selection.rows.map((row) => row.id);
            expect(new Set(ids).size).toBe(ids.length);
            // The opening row is never also present among the ordinary rows.
            if (selection.openingRow) {
                expect(ids).not.toContain(selection.openingRow.id);
            }
        });

        it("preserves chronological order", () => {
            const dates = selection.rows.map((row) => row.date);
            expect(dates).toEqual([...dates].sort());
            const expectedOrder = testCase.transactions
                .filter(isDisplayRow)
                .map((row) => row.id);
            expect(selection.rows.map((row) => row.id)).toEqual(expectedOrder);
        });

        it("is empty in every sense only for the no-data case", () => {
            const isEmptyState = selection.rows.length === 0 && selection.openingRow === null;
            expect(isEmptyState).toBe(!testCase.purchase && !testCase.sale && !testCase.opening);
        });
    });
});

describe.each(MATRIX)("createDisplayRowFilter — $label", (testCase) => {
    const isPrintable = createDisplayRowFilter(testCase.transactions);

    it("keeps exactly the rows that should be rendered", () => {
        const kept = testCase.transactions.filter(isPrintable);
        const expected = testCase.expectedOpeningRow
            ? [testCase.expectedOpeningRow, ...testCase.expectedRows]
            : testCase.expectedRows;
        // Order follows the input collection, not the expectation list.
        expect(kept.map((row) => row.id).sort()).toEqual(expected.map((row) => row.id).sort());
    });

    it("suppresses the opening row exactly when a purchase exists", () => {
        expect(isPrintable(OPENING)).toBe(testCase.opening && !testCase.purchase);
    });
});

// ─── Shim / robustness ──────────────────────────────────────────────────────

describe("selectLedgerDisplayRows edge cases", () => {
    it("returns an empty selection for missing or malformed payloads", () => {
        expect(selectLedgerDisplayRows(null)).toEqual({ rows: [], openingRow: null });
        expect(selectLedgerDisplayRows(undefined)).toEqual({ rows: [], openingRow: null });
        expect(selectLedgerDisplayRows({})).toEqual({ rows: [], openingRow: null });
        expect(selectLedgerDisplayRows({ transactions: null })).toEqual({ rows: [], openingRow: null });
    });

    it("prefers the canonical fields over the shim when both are available", () => {
        const selection = selectLedgerDisplayRows<Row>({
            transactions: [OPENING, PURCHASE, SALE_A],
            display_transactions: [SALE_A],
            opening_display: null,
        });
        expect(selection.rows).toEqual([SALE_A]);
        expect(selection.openingRow).toBeNull();
    });

    it("copies the canonical row list instead of aliasing it", () => {
        const displayTransactions = [PURCHASE];
        const selection = selectLedgerDisplayRows<Row>({ display_transactions: displayTransactions });
        expect(selection.rows).not.toBe(displayTransactions);
        expect(selection.rows).toEqual(displayTransactions);
    });

    it("drops commission rows and never lets them stand in for a purchase", () => {
        const selection = selectDisplayRowsFromTransactions<Row>([OPENING, COMMISSION, SALE_A]);
        expect(selection.rows).toEqual([SALE_A]);
        // COMMISSION is not in PURCHASE_PRESENCE_TYPES, so the opening survives.
        expect(selection.openingRow).toEqual(OPENING);
    });

    it("does not mutate the input collection", () => {
        const transactions = [OPENING, PURCHASE, SALE_A];
        const snapshot = [...transactions];
        selectDisplayRowsFromTransactions(transactions);
        expect(transactions).toEqual(snapshot);
    });
});
