import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { generateExcel, generatePDF } from "../utils/ledgerExport";
import type { CanonicalLedgerResponse } from "../types/canonicalLedger";
import LicenseLedgerDetail, {
    buildLedgerDetailPath,
    getTodayStamp,
    normalizeLedgerDetail,
    sanitizeLedgerFilenamePart,
} from "./LicenseLedgerDetail";

vi.mock("react-router-dom", () => ({
    useLocation: () => ({ search: "", state: null }),
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: "LIC/1", companyId: " 42 " }),
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

const mockedApiGet = vi.mocked(api.get);
const mockedGeneratePDF = vi.mocked(generatePDF);
const mockedGenerateExcel = vi.mocked(generateExcel);

describe("LicenseLedgerDetail helpers", () => {
    it("builds safe ledger-detail API paths from route params", () => {
        expect(buildLedgerDetailPath("LIC/1", " 42 ")).toBe("license-ledger/LIC%2F1/ledger_detail/?company=42");
        expect(buildLedgerDetailPath(" ", "42")).toBeNull();
    });

    it("normalizes canonical ledger responses", () => {
        expect(normalizeLedgerDetail(null)).toBeNull();
        expect(normalizeLedgerDetail({
            license_number: " ",
            license_type: "",
        })).toBeNull();
        // Canonical response should pass through as-is (API is authoritative)
        const canonical: CanonicalLedgerResponse = {
            license_id: 1,
            license_number: "LIC/1",
            license_type: "DFIA",
            license_date: "2026-01-01",
            expiry_date: "2027-01-01",
            exporter_id: 1,
            exporter_name: "Exporter",
            port_id: 1,
            port_name: "Port",
            opening_balance: "0.00",
            license_running_balance: "100.00",
            closing_balance: "100.00",
            transactions: [],
            company_utilizations: {},
            totals: {
                total_purchases: "100.00",
                total_sales: "0.00",
                total_commission: "0.00",
            },
        };
        expect(normalizeLedgerDetail(canonical)).toEqual(canonical);
    });

    it("sanitizes export filename segments and date stamps", () => {
        expect(sanitizeLedgerFilenamePart(' LIC:/<1>" ')).toBe("LIC-1");
        expect(sanitizeLedgerFilenamePart("")).toBe("license");
        expect(getTodayStamp(new Date("2026-07-16T12:30:00Z"))).toBe("2026-07-16");
    });
});

describe("LicenseLedgerDetail", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        mockedGenerateExcel.mockResolvedValue(undefined);
        // Canonical API response (Phase 4C)
        const canonicalResponse: CanonicalLedgerResponse = {
            license_id: 1,
            license_number: "LIC/1",
            license_type: "DFIA",
            license_date: "2026-01-01",
            expiry_date: "2027-01-01",
            exporter_id: 1,
            exporter_name: "Exporter",
            port_id: 1,
            port_name: "Port",
            opening_balance: "0.00",
            license_running_balance: "100.00",
            closing_balance: "100.00",
            transactions: [{
                date: "2026-04-01",
                id: 1,
                type: "PURCHASE",
                company_id: 1,
                company_name: "Acme",
                amount: "100.00",
                is_commission: false,
                affects_balance: true,
                license_running_balance: "100.00",
                company_utilization_after: "100.00",
                display_status: "Active",
            }],
            company_utilizations: {
                "1": {
                    company_id: 1,
                    company_name: "Acme",
                    utilization_balance: "100.00",
                },
            },
            totals: {
                total_purchases: "100.00",
                total_sales: "0.00",
                total_commission: "0.00",
            },
        };
        mockedApiGet.mockResolvedValue({ data: canonicalResponse });
    });

    it("fetches canonical ledger details and exports PDF with a safe filename", async () => {
        render(<LicenseLedgerDetail />);

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("license-ledger/LIC%2F1/ledger_detail/?company=42");
        });
        fireEvent.click(await screen.findByRole("button", { name: /download pdf/i }));

        // Verify PDF export was called with canonical response and safe filename
        expect(mockedGeneratePDF).toHaveBeenCalled();
        const calls = mockedGeneratePDF.mock.calls[0];
        expect(calls[0][0].license_number).toBe("LIC/1");
        expect(calls[0][0].license_type).toBe("DFIA");
        expect(calls[1]).toMatch(/^License_Ledger_LIC-1_.*\.pdf$/);
    });
});
