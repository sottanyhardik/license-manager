import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import LicenseTradingRegisterReport from "./LicenseTradingRegisterReport";

vi.mock("react-router-dom", () => ({
    useNavigate: () => vi.fn(),
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
const REPORT_DATA = {
    dashboard: {
        total_licenses: 1,
        open_licenses: 0,
        closed_licenses: 1,
        total_purchase: "100000.00",
        total_sales: "120000.00",
        total_profit: "20000.00",
        overall_margin_pct: "16.67",
    },
    norms: [
        {
            norm: "E126",
            licenses: [
                {
                    license_id: 1,
                    license_number: "DFIA-E126-1",
                    exporter: "Acme Exports",
                    transactions: [
                        {
                            date: "2026-01-05",
                            direction: "PURCHASE",
                            invoice_number: "INV-1",
                            from_company: "Supplier Co",
                            to_company: "Acme Exports",
                            item: "Vegetable Oil",
                            purchase: "100000.00",
                            sale: "0.00",
                            running_profit: "-100000.00",
                        },
                        {
                            date: "2026-01-10",
                            direction: "SALE",
                            invoice_number: "INV-2",
                            from_company: "Acme Exports",
                            to_company: "Buyer Co",
                            item: "Vegetable Oil",
                            purchase: "0.00",
                            sale: "120000.00",
                            running_profit: "20000.00",
                        },
                    ],
                    summary: {
                        purchase: "100000.00",
                        sales: "120000.00",
                        profit: "20000.00",
                        margin_pct: "16.67",
                        status: "Closed",
                    },
                    item_summary: [
                        {
                            item: "Vegetable Oil",
                            purchase_qty: "500.000",
                            sale_qty: "500.000",
                            purchase_value: "100000.00",
                            sale_value: "120000.00",
                            profit: "20000.00",
                            margin_pct: "16.67",
                        },
                    ],
                },
            ],
            summary: { licenses: 1, purchase: "100000.00", sales: "120000.00", profit: "20000.00", margin_pct: "16.67" },
            item_summary: [
                {
                    item: "Vegetable Oil",
                    licenses: 1,
                    purchase_qty: "500.000",
                    sale_qty: "500.000",
                    purchase_value: "100000.00",
                    sale_value: "120000.00",
                    profit: "20000.00",
                    margin_pct: "16.67",
                },
            ],
        },
    ],
    grand_summary: {
        rows: [{ norm: "E126", licenses: 1, purchase: "100000.00", sales: "120000.00", profit: "20000.00", margin_pct: "16.67" }],
        total: { norm: "Grand Total", licenses: 1, purchase: "100000.00", sales: "120000.00", profit: "20000.00", margin_pct: "16.67" },
    },
    grand_item_summary: {
        rows: [
            {
                norm: "E126",
                item: "Vegetable Oil",
                licenses: 1,
                purchase_qty: "500.000",
                sale_qty: "500.000",
                purchase_value: "100000.00",
                sale_value: "120000.00",
                profit: "20000.00",
            },
        ],
        total: { purchase_value: "100000.00", sale_value: "120000.00", profit: "20000.00" },
    },
};

function mockApi() {
    mockedApiGet.mockImplementation((url: string) => {
        if (url.startsWith("reports/license-trading-register-profit/")) {
            return Promise.resolve({ data: REPORT_DATA });
        }
        return Promise.resolve({ data: {} });
    });
}

describe("LicenseTradingRegisterReport", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApi();
    });

    it("renders every filter and does not load a report before a date range is chosen", () => {
        render(<LicenseTradingRegisterReport />);

        expect(screen.getByText("From")).toBeInTheDocument();
        expect(screen.getByText("To")).toBeInTheDocument();
        expect(screen.getByLabelText("Norm")).toBeInTheDocument();
        expect(screen.getByLabelText("License Type")).toBeInTheDocument();
        expect(screen.getByLabelText("License Number")).toBeInTheDocument();
        expect(screen.getByLabelText("All exporters...")).toBeInTheDocument();
        expect(screen.getByLabelText("All items...")).toBeInTheDocument();
        expect(screen.getByLabelText("All customers...")).toBeInTheDocument();
        expect(screen.getByLabelText("All suppliers...")).toBeInTheDocument();
        expect(screen.getByText("Select a Date Range to View Report")).toBeInTheDocument();
        expect(mockedApiGet).not.toHaveBeenCalled();
    });

    it("loads and renders the dashboard, norm, license and transaction rows once a From/To date is selected", async () => {
        render(<LicenseTradingRegisterReport />);

        fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-01-01" } });
        fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-01-31" } });

        await screen.findAllByText("DFIA-E126-1");

        expect(mockedApiGet).toHaveBeenCalledWith(
            expect.stringContaining("reports/license-trading-register-profit/?format=json&from_date=2026-01-01&to_date=2026-01-31"),
            expect.anything(),
        );

        // Dashboard tiles.
        expect(screen.getByText("Total Licenses")).toBeInTheDocument();
        expect(screen.getByText("Open Licenses")).toBeInTheDocument();
        expect(screen.getByText("Closed Licenses")).toBeInTheDocument();
        expect(screen.getByText("Total Purchase")).toBeInTheDocument();
        expect(screen.getByText("Total Sales")).toBeInTheDocument();
        expect(screen.getByText("Total Profit")).toBeInTheDocument();
        expect(screen.getByText("Overall Margin %")).toBeInTheDocument();

        // Norm section header (first norm is auto-expanded) — "E126" also
        // appears as a <select> option and in the Grand Summary row.
        expect(screen.getAllByText("E126").length).toBeGreaterThan(0);

        // License block header + Transaction Register (first license is
        // auto-expanded too, so the register renders without a manual click).
        expect(screen.getAllByText("DFIA-E126-1").length).toBeGreaterThan(0);
        expect(screen.getByText("INV-1")).toBeInTheDocument();
        expect(screen.getByText("INV-2")).toBeInTheDocument();
        expect(screen.getAllByText("Vegetable Oil").length).toBeGreaterThan(0);

        // License Summary / License Item Summary / Norm Summary / Norm Item Summary.
        expect(screen.getByText("Norm Summary")).toBeInTheDocument();
        expect(screen.getByText("Norm Item Summary")).toBeInTheDocument();

        // Grand Summary / Grand Item Summary.
        expect(screen.getByText("Grand Summary")).toBeInTheDocument();
        expect(screen.getByText("Grand Item Summary")).toBeInTheDocument();
        expect(screen.getAllByText("Grand Total").length).toBeGreaterThan(0);
    });
});
