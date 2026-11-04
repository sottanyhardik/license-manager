import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import LicenseLedger from "./LicenseLedger";

const navigate = vi.fn();
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }));
vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("../services/licenseLedgerExport", () => ({
    previewLicenseLedgerPdf: vi.fn(), downloadLicenseLedgerExcel: vi.fn(), createLicenseLedgerPackage: vi.fn(),
    downloadLicenseLedgerPackage: vi.fn(), downloadCustomLedgerPdf: vi.fn(), relativeApiUrl: (url: string) => url,
    retryLicenseLedgerPackage: vi.fn(),
    licenseLedgerExportError: (_error: unknown, fallback: string) => fallback,
}));
vi.mock("../services/licenseLedgerPackageDownloads", () => ({
    choosePackageDirectory: vi.fn(), loadDownloadState: vi.fn(async () => null),
    SequentialPackageDownloadManager: class {
        onChange?: (state: unknown) => void; onError?: (item: unknown, error: Error) => void;
        constructor(private state: unknown) {} snapshot() { return this.state; } enqueue() {} authorizeDirectory = async () => true;
    },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("../components/AsyncSelectField", () => ({
    default: ({ ariaLabel }: { ariaLabel: string }) => <select aria-label={ariaLabel} />,
}));

const mockedApiGet = vi.mocked(api.get);

const row = (id: number, number: string) => ({
    license_id: id, license_number: number, license_date: "2026-04-01", license_type: "DFIA",
    companies: [{ company_id: 1, company_name: "LABDHI", purchases: [], sales: [], purchase_total: 0, sale_total: 0, profit_loss: 0 }],
});

const metrics = {
    as_of: "2026-11-04",
    total_licences: 2,
    sold_licences: 1,
    partially_sold_licences: 0,
    expired_licences: 0,
    cif_over_utilised_licences: 1,
    review_required_licences: 0,
    incentive_negative_balance_licences: 0,
    cif: { currency: "USD", licence_count: 2, unavailable_count: 0, original: 1500, utilised: 1620, available: -120 },
};

const pagedLedger = {
    licenses: [row(101, "LIC-101")],
    license_ids: ["DFIA:101", "DFIA:102"],
    metrics,
    pagination: { count: 2, page: 1, page_size: 1, total_pages: 2, has_next: true, paginated: true },
};

const summaryData = {
    dfia: { total_licenses: 2, total_value_usd: 0, balance_value_usd: 0, purchase_amount_inr: 0, profit_loss_inr: 0 },
    incentive: { total_licenses: 0, total_value_inr: 0, balance_value_inr: 0, purchase_amount_inr: 0, profit_loss_inr: 0 },
};

function requestsFor(prefix: string): URLSearchParams[] {
    return mockedApiGet.mock.calls
        .filter(([url]) => String(url).startsWith(prefix))
        .map(([url]) => new URL(String(url), "https://test.invalid/").searchParams);
}

describe("LicenseLedger server-side pagination and metrics", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) {
                const page = new URL(url, "https://test.invalid/").searchParams.get("page");
                if (page === "2") {
                    return Promise.resolve({ data: { ...pagedLedger, licenses: [row(102, "LIC-102")], pagination: { ...pagedLedger.pagination, page: 2, has_next: false } } });
                }
                return Promise.resolve({ data: pagedLedger });
            }
            if (url.startsWith("license-ledger/summary/?")) return Promise.resolve({ data: summaryData });
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
    });

    it("shows the metrics strip and keeps negative available CIF visible", async () => {
        render(<LicenseLedger />);
        expect(await screen.findByText("LIC-101")).toBeInTheDocument();
        expect(screen.getByText("Original CIF (USD)")).toBeInTheDocument();
        expect(screen.getByText("$1,500.00")).toBeInTheDocument();
        expect(screen.getByText("Utilised CIF (USD)")).toBeInTheDocument();
        expect(screen.getByText("$1,620.00")).toBeInTheDocument();
        // Negative available CIF is shown as a negative value, never floored to zero.
        expect(screen.getByText("-$120.00")).toBeInTheDocument();
        expect(screen.getByText("Over-utilised (CIF)")).toBeInTheDocument();
    });

    it("requests the next page with the same filters and does not refetch totals", async () => {
        render(<LicenseLedger />);
        expect(await screen.findByText("LIC-101")).toBeInTheDocument();
        const first = requestsFor("license-ledger/license-wise/")[0];
        expect(first.get("page")).toBe("1");
        expect(first.get("page_size")).toBe("50");

        fireEvent.click(screen.getByRole("button", { name: "Next page" }));
        expect(await screen.findByText("LIC-102")).toBeInTheDocument();

        const pages = requestsFor("license-ledger/license-wise/");
        const lastPage = pages[pages.length - 1];
        expect(lastPage.get("page")).toBe("2");
        // Same filter query string on both pages (paging never changes filters).
        const withoutPaging = (params: URLSearchParams) => {
            const copy = new URLSearchParams(params);
            copy.delete("page");
            copy.delete("page_size");
            return copy.toString();
        };
        expect(withoutPaging(lastPage)).toBe(withoutPaging(first));
        // Totals are filter-scoped: the summary request is not repeated for paging.
        // Totals arrive with license-wise, so paging issues no separate summary request.
        expect(requestsFor("license-ledger/summary/?")).toHaveLength(0);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Page 2 of 2"));
        expect(screen.getByText("2", { selector: "[aria-current=\"page\"]" })).toBeInTheDocument();
    });
});

describe("LicenseLedger licence identity", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // One company only: the grand-total bar must still render (previously hidden).
        const licenseRow = (id: number, number: string, type: string) => ({
            license_id: id, license_number: number, license_type: type, license_date: "2026-04-01",
            first_purchase_date: "2026-04-02", sion_norms: "E1", current_balance: 0,
            purchase_bill_inr: 0, sale_bill_inr: 0, profit_loss_inr: 0, has_purchase_bill: true,
        });
        const totals = { total_purchase_bill_inr: 0, total_sale_bill_inr: 0, total_balance: 0, total_profit_loss_inr: 0 };
        const sameNumericId = {
            licenses: [],
            company_groups: [{
                company_id: 1, company_name: "LABDHI", ...totals,
                sion_groups: [{ sion_norm: "E1", sion_label: "SION E1", license_count: 2, ...totals,
                    licenses: [licenseRow(7, "DFIA-7", "DFIA"), licenseRow(7, "INC-7", "RODTEP")] }],
            }],
            grand_total: { license_count: 2, ...totals },
            license_ids: ["DFIA:7", "RODTEP:7"],
            metrics,
            summary: summaryData,
            pagination: { count: 2, page: 1, page_size: 50, total_pages: 1, has_next: false, paginated: true },
        };
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) return Promise.resolve({ data: sameNumericId });
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
    });

    it("never lets a DFIA and an incentive licence with the same numeric id share selection", async () => {
        render(<LicenseLedger />);
        const dfia = await screen.findByRole("checkbox", { name: "Select licence DFIA-7" });
        const incentive = screen.getByRole("checkbox", { name: "Select licence INC-7" });
        // Packages are DFIA-only, so the incentive row cannot be selected for a package.
        expect(incentive).toBeDisabled();
        expect(dfia).toBeEnabled();
        expect(dfia).toBeChecked();
        expect(incentive).not.toBeChecked();
        // Unselecting the DFIA row never touches the incentive row, and vice versa.
        fireEvent.click(dfia);
        expect(dfia).not.toBeChecked();
        expect(incentive).not.toBeChecked();
    });

    it("always shows the grand-total bar and labels licences and rows separately", async () => {
        render(<LicenseLedger />);
        await screen.findByRole("checkbox", { name: "Select licence DFIA-7" });
        expect(screen.getByText(/licence–company rows/)).toBeInTheDocument();
    });
});

describe("LicenseLedger all-filtered selection", () => {
    it("selects every DFIA licence across all pages, not only the visible page", async () => {
        vi.clearAllMocks();
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) return Promise.resolve({ data: pagedLedger });
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
        render(<LicenseLedger />);
        expect(await screen.findByText("LIC-101")).toBeInTheDocument();
        const selectAll = screen.getByRole("button", { name: "Select all 2 DFIA (all pages)" });
        fireEvent.click(selectAll);
        expect(screen.getByText("2 of 2 selected")).toBeInTheDocument();
    });
});

describe("LicenseLedger detail navigation identity", () => {
    it("opens an incentive licence's detail with its own licence type, never the DFIA default", async () => {
        vi.clearAllMocks();
        const licenseRow = (id: number, number: string, type: string) => ({
            license_id: id, license_number: number, license_type: type, license_date: "2026-04-01",
            first_purchase_date: "2026-04-02", sion_norms: "E1", current_balance: 0,
            purchase_bill_inr: 0, sale_bill_inr: 0, profit_loss_inr: 0, has_purchase_bill: true,
        });
        const totals = { total_purchase_bill_inr: 0, total_sale_bill_inr: 0, total_balance: 0, total_profit_loss_inr: 0 };
        mockedApiGet.mockImplementation((url: string) => {
            if (url.startsWith("license-ledger/license-wise/?")) {
                return Promise.resolve({ data: {
                    licenses: [], license_ids: ["DFIA:7", "RODTEP:7"],
                    company_groups: [{ company_id: 1, company_name: "LABDHI", ...totals, sion_groups: [{
                        sion_norm: "E1", sion_label: "SION E1", license_count: 2, ...totals,
                        licenses: [licenseRow(7, "DFIA-7", "DFIA"), licenseRow(7, "INC-7", "RODTEP")],
                    }] }],
                    grand_total: { license_count: 2, ...totals },
                } });
            }
            return Promise.reject(new Error(`Unexpected URL: ${url}`));
        });
        render(<LicenseLedger />);
        await screen.findByRole("checkbox", { name: "Select licence INC-7" });
        // Click the Ledger action in the INCENTIVE row itself (same numeric id as the DFIA row).
        const incentiveRow = screen.getByRole("checkbox", { name: "Select licence INC-7" }).closest("tr") as HTMLElement;
        fireEvent.click(within(incentiveRow).getByRole("button", { name: "Ledger" }));
        expect(navigate).toHaveBeenCalled();
        const lastCall = navigate.mock.calls[navigate.mock.calls.length - 1];
        const target = String(lastCall?.[0]);
        expect(target).toContain("/license-ledger/7");
        expect(target).toContain("license_type=RODTEP");
        expect(target).not.toContain("license_type=DFIA");
    });
});
