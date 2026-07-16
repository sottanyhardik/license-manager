import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { generateExcel, generatePDF } from "../utils/ledgerExport";
import LicenseLedger, {
    buildLedgerFilterParams,
    getCompanyFilterValue,
    getFinancialYearRange,
    getTodayStamp,
    normalizeLicenseWiseData,
    normalizeMinBalance,
} from "./LicenseLedger";

vi.mock("react-router-dom", () => ({
    useNavigate: () => vi.fn(),
}));

vi.mock("../api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));

vi.mock("../utils/ledgerExport", () => ({
    generatePDF: vi.fn(),
    generateExcel: vi.fn(),
}));

vi.mock("sonner", () => ({
    toast: {
        dismiss: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
        success: vi.fn(),
    },
}));

const mockedApiGet = vi.mocked(api.get);
const mockedGeneratePDF = vi.mocked(generatePDF);
const mockedGenerateExcel = vi.mocked(generateExcel);

describe("LicenseLedger helpers", () => {
    it("calculates current and previous financial-year ranges", () => {
        expect(getFinancialYearRange(new Date("2026-07-16T00:00:00Z"))).toEqual({
            fyStart: "2026-04-01",
            fyEnd: "2027-03-31",
        });
        expect(getFinancialYearRange(new Date("2026-02-10T00:00:00Z"))).toEqual({
            fyStart: "2025-04-01",
            fyEnd: "2026-03-31",
        });
        expect(getFinancialYearRange(new Date("2026-07-16T00:00:00Z"), -1)).toEqual({
            fyStart: "2025-04-01",
            fyEnd: "2026-03-31",
        });
    });

    it("normalizes ledger filters before building query parameters", () => {
        const params = buildLedgerFilterParams({
            license_type: "BAD",
            min_balance: "-5",
            search: " LIC 1 ",
            company: { value: " 42 ", label: "Acme" },
            active_only: true,
            ordering: "bad",
            purchase_date_from: "2026-04-01",
            purchase_date_to: "2027-03-31",
            no_purchases: true,
        });

        expect(params.get("license_type")).toBe("ALL");
        expect(params.has("min_balance")).toBe(false);
        expect(params.get("search")).toBe("LIC 1");
        expect(params.get("company")).toBe("42");
        expect(params.get("ordering")).toBe("-license_date");
        expect(params.get("no_purchases")).toBe("true");
    });

    it("normalizes company and numeric filter edge cases", () => {
        expect(getCompanyFilterValue(null)).toBe("");
        expect(getCompanyFilterValue({ value: " 7 " })).toBe("7");
        expect(normalizeMinBalance("100.50")).toBe("100.5");
        expect(normalizeMinBalance("bad")).toBe("");
    });

    it("filters malformed license-wise API rows before rendering/export", () => {
        expect(normalizeLicenseWiseData({
            licenses: [
                null,
                { license_id: "", companies: [] },
                {
                    license_id: "1",
                    license_number: " LIC-1 ",
                    license_date: "",
                    license_type: "DFIA",
                    companies: [{
                        company_id: null,
                        company_name: "",
                        purchases: [{ trade_id: "p1", invoice_date: "2026-04-01", amount: "12.4" }, "bad"],
                        sales: [{ trade_id: "s1", invoice_date: null, amount: "bad" }],
                        purchase_total: "12.4",
                        sale_total: "bad",
                        profit_loss: "-2",
                    }],
                },
            ],
        })).toEqual({
            licenses: [{
                license_id: "1",
                license_number: "LIC-1",
                license_date: "-",
                license_type: "DFIA",
                companies: [{
                    company_id: 0,
                    company_name: "Unknown company",
                    purchases: [{ trade_id: "p1", invoice_date: "2026-04-01", amount: 12.4 }],
                    sales: [{ trade_id: "s1", invoice_date: "-", amount: 0 }],
                    purchase_total: 12.4,
                    sale_total: 0,
                    profit_loss: -2,
                }],
            }],
        });
    });

    it("formats deterministic export date stamps", () => {
        expect(getTodayStamp(new Date("2026-07-16T12:30:00Z"))).toBe("2026-07-16");
    });
});

describe("LicenseLedger", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        mockedGenerateExcel.mockResolvedValue(undefined);
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/")) {
                return Promise.resolve({
                    data: {
                        licenses: [{
                            license_id: 1,
                            license_number: "LIC-1",
                            license_date: "2026-04-01",
                            license_type: "DFIA",
                            companies: [],
                        }],
                    },
                });
            }
            if (url === "license-ledger/1/ledger_detail/") {
                return Promise.resolve({ data: { license_id: 1, license_number: "LIC-1" } });
            }
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
    });

    it("exports normalized license-wise ledger details to PDF", async () => {
        render(<LicenseLedger />);

        fireEvent.click(await screen.findByRole("button", { name: "Export license ledger as PDF" }));

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("license-ledger/1/ledger_detail/");
        });
        expect(mockedGeneratePDF).toHaveBeenCalledWith(
            [{ license_id: 1, license_number: "LIC-1" }],
            expect.stringMatching(/^License_Ledger_Bulk_\d{4}-\d{2}-\d{2}\.pdf$/),
        );
    });
});
