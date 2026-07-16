import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { generateExcel, generatePDF } from "../utils/ledgerExport";
import LicenseLedgerDetail, {
    buildLedgerDetailPath,
    getTodayStamp,
    groupTransactionsByCompany,
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

    it("normalizes malformed ledger detail responses", () => {
        expect(normalizeLedgerDetail(null)).toBeNull();
        expect(normalizeLedgerDetail({
            license_number: " LIC/1 ",
            license_type: "",
            available_balance: "bad",
            total_value: "25.5",
            transactions: [
                { type: "", company_id: 7, company_name: "", debit_amount: "10" },
                "skip",
            ],
        })).toMatchObject({
            license_number: "LIC/1",
            license_type: "UNKNOWN",
            available_balance: 0,
            total_value: 25.5,
            transactions: [{ type: "UNKNOWN", company_id: 7, company_name: "N/A", debit_amount: "10" }],
        });
    });

    it("sanitizes export filename segments and date stamps", () => {
        expect(sanitizeLedgerFilenamePart(' LIC:/<1>" ')).toBe("LIC-1");
        expect(sanitizeLedgerFilenamePart("")).toBe("license");
        expect(getTodayStamp(new Date("2026-07-16T12:30:00Z"))).toBe("2026-07-16");
    });

    it("groups transactions by company without merging unknown companies", () => {
        expect(groupTransactionsByCompany([
            { company_id: null, company_name: "", type: "SALE" },
            { company_id: null, company_name: "", type: "PURCHASE" },
            { company_id: 1, company_name: "Acme", type: "SALE" },
        ])).toHaveLength(3);
    });
});

describe("LicenseLedgerDetail", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        mockedGenerateExcel.mockResolvedValue(undefined);
        mockedApiGet.mockResolvedValue({
            data: {
                license_number: "LIC/1",
                license_type: "DFIA",
                exporter: "Exporter",
                available_balance: 100,
                total_value: 250,
                transactions: [{
                    type: "PURCHASE",
                    company_id: 1,
                    company_name: "Acme",
                    date: "2026-04-01",
                    particular: "Purchase",
                    debit_cif: 100,
                    debit_amount: 1000,
                }],
            },
        });
    });

    it("fetches normalized ledger details and exports PDF with a safe filename", async () => {
        render(<LicenseLedgerDetail />);

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("license-ledger/LIC%2F1/ledger_detail/?company=42");
        });
        fireEvent.click(await screen.findByRole("button", { name: /download pdf/i }));

        expect(mockedGeneratePDF).toHaveBeenCalledWith(
            [expect.objectContaining({ license_number: "LIC/1", license_type: "DFIA" })],
            expect.stringMatching(/^License_Ledger_LIC-1_\d{4}-\d{2}-\d{2}\.pdf$/),
        );
    });
});
