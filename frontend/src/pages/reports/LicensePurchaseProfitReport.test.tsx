import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import LicensePurchaseProfitReport from "./LicensePurchaseProfitReport";

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
    norms: [
        {
            norm: "E126",
            licenses: [
                {
                    license_id: 1,
                    license_number: "DFIA-E126-1",
                    exporter: "Acme Exports",
                    purchase_cost: "100000.00",
                    debited_cif: "90000.00",
                    remaining_cif: "5000.00",
                    allocated_purchase: "100000.00",
                    realized_profit: "-10000.00",
                    profit_pct: "-10.00",
                },
            ],
            items: [
                {
                    license_id: 1,
                    license_number: "DFIA-E126-1",
                    item: "Vegetable Oil",
                    qty_debited: "500.000",
                    debited_cif: "45000.00",
                    pct_share: "50.00",
                    allocated_purchase: "50000.00",
                    profit: "-5000.00",
                },
            ],
            summary: {
                total_purchase: "100000.00",
                total_debited_cif: "90000.00",
                total_profit: "-10000.00",
                margin_pct: "-10.00",
            },
        },
    ],
    grand_summary: {
        rows: [{ norm: "E126", purchase: "100000.00", debited_cif: "90000.00", profit: "-10000.00", margin_pct: "-10.00" }],
        total: { norm: "Grand Total", purchase: "100000.00", debited_cif: "90000.00", profit: "-10000.00", margin_pct: "-10.00" },
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

describe("LicensePurchaseProfitReport", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApi();
    });

    it("renders filters and does not load a report before a date range is chosen", () => {
        render(<LicensePurchaseProfitReport />);

        expect(screen.getByText("From")).toBeInTheDocument();
        expect(screen.getByText("To")).toBeInTheDocument();
        expect(screen.getByLabelText("Norm")).toBeInTheDocument();
        expect(screen.getByLabelText("License Number")).toBeInTheDocument();
        expect(screen.getByLabelText("All exporters...")).toBeInTheDocument();
        expect(screen.getByText("Select a Date Range to View Report")).toBeInTheDocument();
        expect(mockedApiGet).not.toHaveBeenCalled();
    });

    it("loads and renders the report sections once a From/To date is selected", async () => {
        render(<LicensePurchaseProfitReport />);

        fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-01-01" } });
        fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-01-31" } });

        await screen.findAllByText("DFIA-E126-1");

        expect(mockedApiGet).toHaveBeenCalledWith(
            expect.stringContaining("reports/license-purchase-profit/?format=json&from_date=2026-01-01&to_date=2026-01-31"),
            expect.anything(),
        );

        // Norm section header + all three tables.
        expect(screen.getByText("License Summary")).toBeInTheDocument();
        expect(screen.getByText("Item-wise Profit")).toBeInTheDocument();
        expect(screen.getByText("Norm Summary")).toBeInTheDocument();
        expect(screen.getByText("Vegetable Oil")).toBeInTheDocument();
        expect(screen.getByText("Acme Exports")).toBeInTheDocument();

        // Grand Summary section.
        expect(screen.getByText("Grand Summary")).toBeInTheDocument();
        expect(screen.getByText("Grand Total")).toBeInTheDocument();
    });
});
