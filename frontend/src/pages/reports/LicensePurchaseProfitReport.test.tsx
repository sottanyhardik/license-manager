import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import LicensePurchaseProfitReport from "./LicensePurchaseProfitReport";

const mockSetSearchParams = vi.fn();

vi.mock("react-router-dom", () => ({
    useNavigate: () => vi.fn(),
    useSearchParams: () => [new URLSearchParams(), mockSetSearchParams],
}));

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
        info: vi.fn(),
    },
}));

vi.mock("@/components/AsyncSelectField", () => ({
    default: ({ placeholder }: { placeholder?: string }) => <input aria-label={placeholder} readOnly />,
}));

const mockedApiGet = vi.mocked(api.get);

// Numbers arrive as Decimal-safe strings from the API — the UI must parse
// them with Number(...) rather than assume they're already JS numbers.
// The mocked `summary` block deliberately does NOT equal the naive sum of
// the mocked `licenses` rows below, so any test asserting the summary
// cards show `summary`'s numbers (not a client-recomputed sum) is
// actually exercising the Builder→DTO contract.
//
// `item_matrix.totals` similarly does NOT equal a naive sum of
// `item_matrix.rows` below (e.g. ALMOND's mocked total qty/cif/bill is
// deliberately larger than the single mocked row would sum to) — this
// catches any accidental client-side `.reduce()` recompute of the
// grand-total row.
const REPORT_DATA = {
    summary: {
        total_licenses: 5,
        purchase_amount: "999999.00",
        purchase_usd: "8888.00",
        balance_cif: "7777.00",
        total_sale_usd: "6543.21",
        total_sale_amount: "543210.99",
        total_profit_loss: "-4321.55",
    },
    licenses: [
        {
            license_number: "DFIA-E126-1",
            license_date: "2026-01-05",
            expiry_date: "2027-01-04",
            exporter: "Acme Exports",
            norms: ["E126", "E132"],
            purchase_from: "Global Supplies Ltd",
            purchase_amount: "100000.00",
            purchase_usd: "1200.00",
            sale_amount: "90000.00",
            sale_usd: "1100.00",
            profit_loss: "-10000.00",
            balance_cif: "300.00",
        },
    ],
    item_matrix: {
        headers: ["ALMOND", "CASHEW"],
        rows: [
            {
                license_number: "DFIA-E126-1",
                license_date: "2026-01-05",
                expiry_date: "2027-01-04",
                exporter: "Acme Exports",
                norms: ["E126", "E132"],
                purchase_from: "Global Supplies Ltd",
                purchase_amount: "100000.00",
                purchase_usd: "1200.00",
                sale_amount: "90000.00",
                sale_usd: "1100.00",
                profit_loss: "-10000.00",
                balance_cif: "300.00",
                items: {
                    // Real debit for ALMOND on this license.
                    ALMOND: { qty: 150.5, cif: 400.25, bill: 30000.5 },
                    // CASHEW has no debit against this license at all — must
                    // zero-fill rather than omit the key.
                    CASHEW: { qty: 0, cif: 0, bill: 0 },
                },
            },
        ],
        // Deliberately NOT equal to the single row's own qty/cif/bill above —
        // proves the grand-total row reads this verbatim instead of
        // recomputing from `rows`.
        totals: {
            ALMOND: { qty: 999.111, cif: 5000.75, bill: 400000.25 },
            CASHEW: { qty: 42, cif: 10.5, bill: 999.99 },
        },
    },
};

function mockApi() {
    mockedApiGet.mockImplementation((url: string) => {
        if (url.startsWith("reports/license-purchase-profit/")) {
            return Promise.resolve({ data: REPORT_DATA });
        }
        return Promise.resolve({ data: {} });
    });
}

function pickDateRange() {
    fireEvent.change(screen.getByLabelText("From Date"), { target: { value: "2026-01-01" } });
    fireEvent.change(screen.getByLabelText("To Date"), { target: { value: "2026-01-31" } });
}

/** Flush pending microtasks (the mocked `api.get()` promise resolution)
 * inside `act` so the resulting `setState` calls are applied before the
 * next assertion. */
async function flushMicrotasks() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("LicensePurchaseProfitReport", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        sessionStorage.clear();
        mockApi();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("renders every filter and does not fetch before a date range is chosen", () => {
        render(<LicensePurchaseProfitReport />);

        expect(screen.getByLabelText("From Date")).toBeInTheDocument();
        expect(screen.getByLabelText("To Date")).toBeInTheDocument();
        expect(screen.getByLabelText("Norm")).toBeInTheDocument();
        expect(screen.getByLabelText("License Number")).toBeInTheDocument();
        expect(screen.getByLabelText("Exclude License Number")).toBeInTheDocument();
        expect(screen.getByLabelText("All exporters...")).toBeInTheDocument();
        expect(screen.getByText("Select a date range to view the report.")).toBeInTheDocument();
        expect(mockedApiGet).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: /Apply Filters/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Generate Report/i })).not.toBeInTheDocument();
    });

    it("auto-fetches as soon as both From and To Date are set — no Apply click needed", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        expect(mockedApiGet).toHaveBeenCalledWith(
            expect.stringContaining("reports/license-purchase-profit/?format=json&from_date=2026-01-01&to_date=2026-01-31"),
            expect.anything(),
        );
        expect(mockedApiGet).toHaveBeenCalledTimes(1);

        expect(await screen.findAllByText("DFIA-E126-1")).not.toHaveLength(0);
        expect(screen.getByText("License Summary")).toBeInTheDocument();
        // "Acme Exports" now also appears in the Item Utilization Matrix's
        // own Exporter column, so this can no longer assume a single match.
        expect(screen.getAllByText("Acme Exports").length).toBeGreaterThan(0);
        // Two tables now render (License Summary, then the Item
        // Utilization Matrix below it) — scope to the first (License
        // Summary, which renders first in the JSX) to keep the assertion
        // unambiguous.
        const table = screen.getAllByRole("table")[0];
        expect(within(table).getByText("E126")).toBeInTheDocument();
        expect(within(table).getByText("E132")).toBeInTheDocument();
        expect(screen.queryByText("Item-wise Profit")).not.toBeInTheDocument();
        expect(screen.queryByText("Norm Summary")).not.toBeInTheDocument();
        expect(screen.queryByText("Grand Summary")).not.toBeInTheDocument();
    });

    it("renders the Purchase From and Balance CIF ($) columns", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // "Purchase From" and "Global Supplies Ltd" also appear in the Item
        // Utilization Matrix's own static columns now, so these can no
        // longer assume a single match.
        expect(screen.getAllByText("Purchase From").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Balance CIF ($)").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Global Supplies Ltd").length).toBeGreaterThan(0);
    });

    it("shows the summary cards' own totals, not a client-recomputed sum of the rows", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // These come from the mocked `summary` block, which deliberately
        // differs from the (single-row) `licenses` totals.
        expect(screen.getByText("Total Licenses")).toBeInTheDocument();
        expect(screen.getByText("5")).toBeInTheDocument();
        expect(screen.getAllByText("Balance CIF ($)").length).toBeGreaterThan(0);
        // These also now appear a second time, verbatim, in the License
        // Summary table's own grand-total footer row — hence `getAllByText`
        // rather than `getByText` here.
        expect(screen.getAllByText("7,777.00").length).toBeGreaterThan(0);
        expect(screen.getAllByText("8,888.00").length).toBeGreaterThan(0);
        expect(screen.getAllByText("9,99,999.00").length).toBeGreaterThan(0);
    });

    it("renders the 6 currency summary cards' exact primary values plus a full-precision title tooltip", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // Primary values are unchanged by the new secondaryValue/title props —
        // still the exact money()-formatted figure from the mocked summary.
        expect(screen.getAllByText("9,99,999.00").length).toBeGreaterThan(0);
        expect(screen.getAllByText("8,888.00").length).toBeGreaterThan(0);
        expect(screen.getAllByText("5,43,210.99").length).toBeGreaterThan(0);
        expect(screen.getAllByText("6,543.21").length).toBeGreaterThan(0);
        expect(screen.getAllByText("-4,321.55").length).toBeGreaterThan(0);
        expect(screen.getAllByText("7,777.00").length).toBeGreaterThan(0);

        // The summary card's value element carries a native `title=""`
        // attribute with the same full-precision figure (this codebase's
        // own tooltip convention — never the shadcn Tooltip component).
        // "9,99,999.00" also appears a second time, verbatim, in the table's
        // grand-total footer (which has no `title` attribute), hence
        // checking all matches rather than assuming a single one.
        const purchaseAmountMatches = screen.getAllByText("9,99,999.00");
        expect(purchaseAmountMatches.some((el) => el.getAttribute("title") === "9,99,999.00")).toBe(true);

        // Purchase Amount (999999.00) is Lakh-range — its secondary,
        // abbreviated line renders under the primary value.
        expect(screen.getByText("10.00 L")).toBeInTheDocument();

        // Total Licenses stays a plain count — no title attribute, since
        // neither `secondaryValue` nor `title` is passed for it.
        expect(screen.getByText("5")).not.toHaveAttribute("title");
    });

    it("debounces License Number ~400ms before re-fetching, firing exactly one extra request", async () => {
        vi.useFakeTimers();
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();
        expect(mockedApiGet).toHaveBeenCalledTimes(1);

        fireEvent.change(screen.getByLabelText("License Number"), { target: { value: "DFIA" } });

        // Still inside the debounce window — no new request yet.
        await act(async () => {
            vi.advanceTimersByTime(300);
            await Promise.resolve();
        });
        expect(mockedApiGet).toHaveBeenCalledTimes(1);

        // Past the 400ms debounce — exactly one new request fires.
        await act(async () => {
            vi.advanceTimersByTime(150);
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(mockedApiGet).toHaveBeenCalledTimes(2);
        expect(mockedApiGet).toHaveBeenLastCalledWith(
            expect.stringContaining("license_number=DFIA"),
            expect.anything(),
        );
    });

    it("sends exclude_license_number chips added via Enter, debounced the same as License Number", async () => {
        vi.useFakeTimers();
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        const excludeInput = screen.getByLabelText("Exclude License Number");
        fireEvent.change(excludeInput, { target: { value: "DFIA-2" } });
        fireEvent.keyDown(excludeInput, { key: "Enter" });
        fireEvent.change(excludeInput, { target: { value: "DFIA-3" } });
        fireEvent.keyDown(excludeInput, { key: "Enter" });

        await act(async () => {
            vi.advanceTimersByTime(400);
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(mockedApiGet).toHaveBeenLastCalledWith(
            expect.stringContaining("exclude_license_number=DFIA-2%2CDFIA-3"),
            expect.anything(),
        );
    });

    it("Reset clears filters and the loaded report", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();
        expect(await screen.findAllByText("DFIA-E126-1")).not.toHaveLength(0);

        fireEvent.click(screen.getByRole("button", { name: /Reset/i }));

        expect(screen.getByText("Select a date range to view the report.")).toBeInTheDocument();
        expect((screen.getByLabelText("From Date") as HTMLInputElement).value).toBe("");
    });

    it("shows a friendly error with a Retry button on a failed fetch, and Retry re-triggers it", async () => {
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("reports/license-purchase-profit/")) {
                return Promise.reject({ response: { status: 404, data: { error: "No matching licenses." } } });
            }
            return Promise.resolve({ data: {} });
        });

        render(<LicensePurchaseProfitReport />);
        pickDateRange();
        await flushMicrotasks();

        expect(screen.getByText("Failed to Load Report")).toBeInTheDocument();
        expect(screen.getByText("No matching licenses.")).toBeInTheDocument();

        mockApi();
        fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
        await flushMicrotasks();

        expect(await screen.findAllByText("DFIA-E126-1")).not.toHaveLength(0);
    });

    it("shows the summary cards from summary.total_sale_usd / total_sale_amount / total_profit_loss", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // These values also now appear a second time, verbatim, in the
        // License Summary table's own grand-total footer row — hence
        // `getAllByText` rather than `getByText` for the figures.
        expect(screen.getByText("Total Sale $")).toBeInTheDocument();
        expect(screen.getAllByText("6,543.21").length).toBeGreaterThan(0);
        expect(screen.getByText("Total Sale Amount")).toBeInTheDocument();
        expect(screen.getAllByText("5,43,210.99").length).toBeGreaterThan(0);
        // Deliberately negative — proves a real loss renders with the minus
        // sign rather than as a formatting error.
        expect(screen.getByText("Total Profit / Loss")).toBeInTheDocument();
        expect(screen.getAllByText("-4,321.55").length).toBeGreaterThan(0);
    });

    it("renders the 3 new License Summary columns (Sale Amount, Sale $, Profit / Loss), including a negative Profit/Loss", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        const table = screen.getAllByRole("table")[0];
        expect(within(table).getByText("Sale Amount")).toBeInTheDocument();
        expect(within(table).getByText("Sale $")).toBeInTheDocument();
        expect(within(table).getByText("Profit / Loss")).toBeInTheDocument();

        // DFIA-E126-1's mocked row: sale_amount 90000.00, sale_usd 1100.00,
        // profit_loss -10000.00 (a real loss — must render with a minus sign).
        expect(within(table).getByText("90,000.00")).toBeInTheDocument();
        expect(within(table).getByText("1,100.00")).toBeInTheDocument();
        expect(within(table).getByText("-10,000.00")).toBeInTheDocument();
    });

    it("renders a sticky grand-total footer row on the License Summary table, reading summary verbatim (not a client-recomputed sum of the rows)", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        const table = screen.getAllByRole("table")[0];
        expect(within(table).getByText("Grand Total")).toBeInTheDocument();

        // These are the mocked `summary` totals, deliberately different from
        // the single mocked row's own purchase/sale/profit-loss figures
        // above (100000.00/1200.00/90000.00/1100.00/-10000.00/300.00) — a
        // footer built by summing `licenses` would show the row's own
        // figures here instead and this assertion would fail.
        expect(within(table).getByText("9,99,999.00")).toBeInTheDocument();
        expect(within(table).getByText("8,888.00")).toBeInTheDocument();
        expect(within(table).getByText("5,43,210.99")).toBeInTheDocument();
        expect(within(table).getByText("6,543.21")).toBeInTheDocument();
        expect(within(table).getByText("-4,321.55")).toBeInTheDocument();
        expect(within(table).getByText("7,777.00")).toBeInTheDocument();
    });

    it("renders the Item Utilization Matrix's grouped headers with the right colSpan", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        expect(screen.getByText("Item Utilization Matrix")).toBeInTheDocument();
        const almondHeader = screen.getByRole("columnheader", { name: "ALMOND" });
        expect(almondHeader).toHaveAttribute("colspan", "3");
        const cashewHeader = screen.getByRole("columnheader", { name: "CASHEW" });
        expect(cashewHeader).toHaveAttribute("colspan", "3");
        expect(screen.getAllByRole("columnheader", { name: "Qty" })).toHaveLength(2);
        expect(screen.getAllByRole("columnheader", { name: "CIF $" })).toHaveLength(2);
        expect(screen.getAllByRole("columnheader", { name: "Bill ₹" })).toHaveLength(2);
    });

    it("renders the Sale Amount/Sale $/Profit-Loss static columns on the Item Utilization Matrix too, including the negative Profit/Loss", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // Scope to the second table (Item Utilization Matrix) — the first
        // table (License Summary) already has its own Sale Amount/Sale $/
        // Profit-Loss columns covered by a separate test.
        const matrixTable = screen.getAllByRole("table")[1];
        expect(within(matrixTable).getByText("Sale Amount")).toBeInTheDocument();
        expect(within(matrixTable).getByText("Sale $")).toBeInTheDocument();
        expect(within(matrixTable).getByText("Profit / Loss")).toBeInTheDocument();

        // Same underlying license row as the License Summary table (the
        // real DTO spreads the same license fields into item_matrix.rows),
        // so the mocked figures are identical: 90,000.00 / 1,100.00 /
        // -10,000.00 (a real loss — must render with a minus sign here too).
        expect(within(matrixTable).getByText("90,000.00")).toBeInTheDocument();
        expect(within(matrixTable).getByText("1,100.00")).toBeInTheDocument();
        expect(within(matrixTable).getByText("-10,000.00")).toBeInTheDocument();
    });

    it("renders per-license item qty/cif/bill cells, including a zero-filled cell for an item with no debit", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // ALMOND has a real debit on this license: qty 150.500, cif 400.25, bill 30,000.50.
        expect(screen.getByText("150.500")).toBeInTheDocument();
        expect(screen.getByText("400.25")).toBeInTheDocument();
        expect(screen.getByText("30,000.50")).toBeInTheDocument();

        // CASHEW has zero debit on this license — must render zero-filled
        // cells, not omit them.
        expect(screen.getAllByText("0.000").length).toBeGreaterThan(0);
    });

    it("shows the matrix's grand-total row exactly as mocked in item_matrix.totals, not a client-recomputed sum", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        // The License Summary table now has its own "Grand Total" footer
        // row too, so there are 2 matches — `getAllByText` rather than
        // `getByText`.
        expect(screen.getAllByText("Grand Total").length).toBeGreaterThan(0);
        // ALMOND totals: qty 999.111, cif 5,000.75, bill 4,00,000.25 —
        // deliberately different from the single row's own ALMOND figures
        // (150.500 / 400.25 / 30,000.50) asserted above.
        expect(screen.getByText("999.111")).toBeInTheDocument();
        expect(screen.getByText("5,000.75")).toBeInTheDocument();
        expect(screen.getByText("4,00,000.25")).toBeInTheDocument();
        // CASHEW totals: qty 42.000, cif 10.50, bill 999.99.
        expect(screen.getByText("42.000")).toBeInTheDocument();
        expect(screen.getByText("10.50")).toBeInTheDocument();
        expect(screen.getByText("999.99")).toBeInTheDocument();
    });

    it("shows the matrix's Grand Total row's static column totals from summary, not blank/spanned-over", async () => {
        render(<LicensePurchaseProfitReport />);

        pickDateRange();
        await flushMicrotasks();

        const matrixTable = screen.getAllByRole("table")[1];
        expect(within(matrixTable).getByText("Grand Total")).toBeInTheDocument();

        // Same mocked `summary` totals the License Summary table's own
        // footer shows (9,99,999.00 / 8,888.00 / 5,43,210.99 / 6,543.21 /
        // -4,321.55 / 7,777.00) — deliberately different from the single
        // mocked row's own purchase/sale/profit-loss/balance figures, so a
        // footer built by summing `rows` instead of reading `summary`
        // would show the row's own numbers here and this would fail.
        expect(within(matrixTable).getByText("9,99,999.00")).toBeInTheDocument();
        expect(within(matrixTable).getByText("8,888.00")).toBeInTheDocument();
        expect(within(matrixTable).getByText("5,43,210.99")).toBeInTheDocument();
        expect(within(matrixTable).getByText("6,543.21")).toBeInTheDocument();
        expect(within(matrixTable).getByText("-4,321.55")).toBeInTheDocument();
        expect(within(matrixTable).getByText("7,777.00")).toBeInTheDocument();
    });

    it("shows a 'No import items to display' message when item_matrix.headers is empty", async () => {
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("reports/license-purchase-profit/")) {
                return Promise.resolve({
                    data: {
                        ...REPORT_DATA,
                        item_matrix: { headers: [], rows: [], totals: {} },
                    },
                });
            }
            return Promise.resolve({ data: {} });
        });

        render(<LicensePurchaseProfitReport />);
        pickDateRange();
        await flushMicrotasks();

        expect(screen.getByText("No import items to display")).toBeInTheDocument();
    });
});
