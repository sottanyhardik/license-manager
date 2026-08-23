import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { downloadLicenseLedgerExcel, previewLicenseLedgerPdf } from "../services/licenseLedgerExport";
import { getFinancialYearRange } from "../utils/dateRangePresets";
import LicenseLedger from "./LicenseLedger";
import { normalizeLicenseWiseData } from "./licenseLedgerData";

const navigate = vi.fn();
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }));
vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("../services/licenseLedgerExport", () => ({
    previewLicenseLedgerPdf: vi.fn(), downloadLicenseLedgerExcel: vi.fn(),
    licenseLedgerExportError: (_error: unknown, fallback: string) => fallback,
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));
vi.mock("../components/AsyncSelectField", () => ({
    default: ({ ariaLabel, value, onChange }: { ariaLabel: string; value: string | number | null; onChange: (value: unknown) => void }) => (
        <select aria-label={ariaLabel} value={value ?? ""} onChange={(event) => onChange(event.target.value || null)}>
            <option value="">All</option><option value="7">Option 7</option><option value="E1">E1</option><option value="GE">GE</option>
        </select>
    ),
}));

const mockedApiGet = vi.mocked(api.get);
const mockedPreviewPdf = vi.mocked(previewLicenseLedgerPdf);
const mockedDownloadExcel = vi.mocked(downloadLicenseLedgerExcel);

const ledgerData = { licenses: [{
    license_id: 2436, license_number: "LIC-2436", license_date: "2026-04-01",
    license_type: "DFIA", companies: [{ company_id: 766, company_name: "LABDHI",
        purchases: [], sales: [], purchase_total: 0, sale_total: 0, profit_loss: 0 }],
}] };
const summaryData = {
    dfia: { total_licenses: 1, total_value_usd: 0, balance_value_usd: 0, purchase_amount_inr: 0, profit_loss_inr: 0 },
    incentive: { total_licenses: 0, total_value_inr: 0, balance_value_inr: 0, purchase_amount_inr: 0, profit_loss_inr: 0 },
};

function queryFor(prefix: string): URLSearchParams {
    const call = [...mockedApiGet.mock.calls].reverse().find(([url]) => String(url).startsWith(prefix));
    if (!call) throw new Error(`No request for ${prefix}`);
    return new URL(String(call[0]), "https://test.invalid/").searchParams;
}

describe("LicenseLedger fresh filters", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) return Promise.resolve({ data: ledgerData });
            if (url.startsWith("license-ledger/summary/?")) return Promise.resolve({ data: summaryData });
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
    });

    it("renders every fresh filter and sends canonical defaults to both endpoints", async () => {
        render(<LicenseLedger />);
        expect(await screen.findByText("LIC-2436")).toBeInTheDocument();
        for (const label of ["Filters & Search", "Company Filter", "Min Balance", "Sort By", "Active Only", "Norm", "Purchase Status", "Purchase Bill Status", "Purchase Date Range"]) {
            expect(screen.getByText(label)).toBeInTheDocument();
        }
        expect(screen.getByPlaceholderText(/license # or exporter/i)).toBeInTheDocument();
        const expectedFy = getFinancialYearRange();
        for (const prefix of ["license-ledger/license-wise/", "license-ledger/summary/"]) {
            const params = queryFor(prefix);
            expect(params.get("license_type")).toBe("ALL");
            expect(params.get("ordering")).toBe("-license_date");
            expect(params.has("active_only")).toBe(false);
            expect(params.get("purchase_date_from")).toBe(expectedFy.fyStart);
            expect(params.get("purchase_date_to")).toBe(expectedFy.fyEnd);
        }
    });

    it("normalizes independent filters into the new API contract", async () => {
        render(<LicenseLedger />);
        await screen.findByText("LIC-2436");
        fireEvent.change(screen.getByLabelText("Company Filter"), { target: { value: "7" } });
        fireEvent.keyDown(screen.getByRole("combobox", { name: "License Type" }), { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "DFIA" }));
        fireEvent.change(screen.getByLabelText("Min Balance"), { target: { value: "1000" } });
        fireEvent.click(screen.getByRole("switch", { name: "Active Only" }));
        fireEvent.change(screen.getByLabelText("Norm"), { target: { value: "E1" } });
        fireEvent.change(screen.getByLabelText("Purchase Status"), { target: { value: "GE" } });
        fireEvent.click(screen.getByRole("button", { name: "With Purchase Bill" }));
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").get("purchase_bill")).toBe("WITH_PURCHASE_BILL"));
        const params = queryFor("license-ledger/license-wise/");
        expect(Object.fromEntries(params)).toMatchObject({ buying_company_id: "7", license_type: "DFIA", min_balance: "1000", active_only: "true", norm: "E1", purchase_status: "GE" });
    });

    it("clears dates independently and Clear All restores current-FY defaults", async () => {
        render(<LicenseLedger />);
        await screen.findByText("LIC-2436");
        fireEvent.click(screen.getByRole("button", { name: /^Clear$/ }));
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").has("purchase_date_from")).toBe(false));
        fireEvent.click(screen.getByRole("button", { name: /clear all/i }));
        const expectedFy = getFinancialYearRange();
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").get("purchase_date_from")).toBe(expectedFy.fyStart));
    });

    it("passes the exact filtered query to both shared exporters", async () => {
        render(<LicenseLedger />);
        await screen.findByText("LIC-2436");
        fireEvent.keyDown(screen.getByRole("combobox", { name: "License Type" }), { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "RODTEP" }));
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").get("license_type")).toBe("RODTEP"));
        fireEvent.click(screen.getByRole("button", { name: /preview pdf/i }));
        await waitFor(() => expect(mockedPreviewPdf).toHaveBeenCalled());
        fireEvent.click(screen.getByRole("button", { name: /download excel/i }));
        await waitFor(() => expect(mockedDownloadExcel).toHaveBeenCalled());
        const pdfParams = mockedPreviewPdf.mock.calls[0][0].params;
        const excelParams = mockedDownloadExcel.mock.calls[0][0].params;
        expect(pdfParams.toString()).toBe(excelParams.toString());
        expect(pdfParams.get("license_type")).toBe("RODTEP");
    });

    it("uses one accessible License Type select and resets it to All Licenses", async () => {
        render(<LicenseLedger />);
        await screen.findByText("LIC-2436");

        const select = screen.getByRole("combobox", { name: "License Type" });
        expect(select).toHaveTextContent("All Licenses");
        expect(screen.queryByRole("button", { name: "DFIA Only" })).not.toBeInTheDocument();

        fireEvent.keyDown(select, { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "MEIS" }));
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").get("license_type")).toBe("MEIS"));

        fireEvent.click(screen.getByRole("button", { name: /clear all/i }));
        await waitFor(() => expect(queryFor("license-ledger/license-wise/").get("license_type")).toBe("ALL"));
        expect(screen.getByRole("combobox", { name: "License Type" })).toHaveTextContent("All Licenses");
    });

    it("sends the canonical ALL_INCENTIVE value for All Incentive", async () => {
        render(<LicenseLedger />);
        await screen.findByText("LIC-2436");

        fireEvent.keyDown(screen.getByRole("combobox", { name: "License Type" }), { key: "ArrowDown" });
        fireEvent.click(screen.getByRole("option", { name: "All Incentive" }));

        await waitFor(() => {
            expect(queryFor("license-ledger/license-wise/").get("license_type")).toBe("ALL_INCENTIVE");
            expect(queryFor("license-ledger/summary/").get("license_type")).toBe("ALL_INCENTIVE");
        });
    });

    it("opens the retained detail route and normalizes malformed rows", async () => {
        render(<LicenseLedger />);
        fireEvent.click(await screen.findByRole("button", { name: /view ledger for LIC-2436/i }));
        expect(navigate).toHaveBeenCalledWith("/license-ledger/2436/766");
        expect(normalizeLicenseWiseData({ licenses: [null, { license_id: "", companies: [] }] })).toEqual({ licenses: [] });
    });

    it("renders the canonical company → SION → license hierarchy without changing financial values", async () => {
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) return Promise.resolve({ data: {
                licenses: [],
                company_groups: [{
                    company_id: 766, company_name: "LABDHI MERCANTILE LLP",
                    total_purchase_bill_inr: "300", total_sale_bill_inr: "450", total_balance: "75", total_profit_loss_inr: "150",
                    sion_groups: [
                        { sion_norm: "E1", sion_label: "E1", license_count: 1, total_purchase_bill_inr: "100", total_sale_bill_inr: "175", total_balance: "25", total_profit_loss_inr: "75",
                            licenses: [{ license_id: 1, license_number: "LIC-E1", license_type: "DFIA", license_date: "2026-01-01", first_purchase_date: "2025-12-01", sion_norms: "E1", current_balance: "25", purchase_bill_inr: "100", sale_bill_inr: "175", profit_loss_inr: "75", has_purchase_bill: false }] },
                        { sion_norm: "E5, E132", sion_label: "E5, E132", license_count: 1, total_purchase_bill_inr: "200", total_sale_bill_inr: "275", total_balance: "50", total_profit_loss_inr: "75",
                            licenses: [{ license_id: 2, license_number: "LIC-MULTI", license_type: "DFIA", license_date: "2026-01-02", first_purchase_date: "2025-12-02", sion_norms: "E5, E132", current_balance: "50", purchase_bill_inr: "200", sale_bill_inr: "275", profit_loss_inr: "75" }] },
                        { sion_norm: "", sion_label: "N/A / EMPTY", license_count: 1, total_purchase_bill_inr: "0", total_sale_bill_inr: "0", total_balance: "0", total_profit_loss_inr: "0", licenses: [] },
                    ],
                }],
            } });
            if (url.startsWith("license-ledger/summary/?")) return Promise.resolve({ data: summaryData });
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });

        render(<LicenseLedger />);
        expect(await screen.findByRole("heading", { name: "LABDHI MERCANTILE LLP" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "SION: E1" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "SION: E5, E132" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "SION: N/A / EMPTY" })).toBeInTheDocument();
        expect(screen.getAllByText("LIC-MULTI")).toHaveLength(1);
        expect(screen.getByText("NO PURCHASE BILL")).toBeInTheDocument();
        expect(screen.getAllByText("₹100.00").length).toBeGreaterThan(0);
        expect(screen.getAllByText("₹175.00").length).toBeGreaterThan(0);
        expect(screen.getByText("Company Total — LABDHI MERCANTILE LLP")).toBeInTheDocument();

        fireEvent.click(screen.getAllByRole("button", { name: "View Ledger" })[0]);
        expect(navigate).toHaveBeenCalledWith("/license-ledger/1/766");
    });
});
