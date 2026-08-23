import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { downloadLicenseLedgerExcel, previewLicenseLedgerPdf } from "../services/licenseLedgerExport";
import type { CanonicalLedgerResponse } from "../types/canonicalLedger";
import LicenseLedgerDetail from "./LicenseLedgerDetail";
import { buildLedgerDetailPath, normalizeLedgerDetail } from "./licenseLedgerDetailUtils";

vi.mock("react-router-dom", () => ({
    useLocation: () => ({ search: "", state: null }),
    useNavigate: () => vi.fn(),
    useParams: () => ({ licenseId: "LIC/1", itemId: " 42 " }),
}));

vi.mock("../api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));
vi.mock("../services/licenseLedgerExport", () => ({
    previewLicenseLedgerPdf: vi.fn(),
    downloadLicenseLedgerExcel: vi.fn(),
    licenseLedgerExportError: (_error: unknown, fallback: string) => fallback,
}));

const mockedApiGet = vi.mocked(api.get);
const mockedPreviewPdf = vi.mocked(previewLicenseLedgerPdf);
const mockedDownloadExcel = vi.mocked(downloadLicenseLedgerExcel);

describe("LicenseLedgerDetail helpers", () => {
    it("builds safe ledger-detail API paths from route params", () => {
        expect(buildLedgerDetailPath("LIC/1", " 42 ")).toBe("license-ledger/LIC%2F1/ledger_detail/?company=42");
        expect(buildLedgerDetailPath("0311051362")).toBe("license-ledger/0311051362/ledger_detail/");
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

});

describe("LicenseLedgerDetail", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
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

    it("fetches canonical details and uses the shared export service", async () => {
        render(<LicenseLedgerDetail />);

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("license-ledger/LIC%2F1/ledger_detail/?company=42");
        });
        expect(await screen.findByText("License Ledger")).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /preview pdf/i }));
        await waitFor(() => expect(mockedPreviewPdf).toHaveBeenCalledWith({ licenseId: "LIC/1", itemId: " 42 ", licenseType: "DFIA" }));
        fireEvent.click(screen.getByRole("button", { name: /download excel/i }));
        await waitFor(() => expect(mockedDownloadExcel).toHaveBeenCalledWith({ licenseId: "LIC/1", itemId: " 42 ", licenseType: "DFIA" }));
    });
});
