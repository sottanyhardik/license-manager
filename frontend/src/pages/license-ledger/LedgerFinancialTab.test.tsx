import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LedgerFinancialTab from "./LedgerFinancialTab";

const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy } }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy } }));
vi.mock("react-router-dom", () => ({ useParams: () => ({}), useNavigate: () => vi.fn(), useLocation: () => ({ search: "", state: null }) }));
vi.mock("../../services/licenseLedgerExport", () => ({ previewLicenseLedgerPdf: vi.fn(), downloadLicenseLedgerExcel: vi.fn(), licenseLedgerExportError: (_e: unknown, f: string) => f }));

const txn = (id: number, type: "PURCHASE" | "SALE") => ({
    date: "2026-05-10", id, type, company_id: 1, company_name: "Acme", amount: "100.00", is_commission: false,
    affects_balance: true, license_running_balance: "100.00", company_utilization_after: "100.00", display_status: "Active",
    party_name: "Party", invoice_number: `INV-${id}`,
    ...(type === "PURCHASE" ? { purchase_amount: "100.00", purchase_bill_amount: "8000.00" } : { sale_amount: "50.00", sale_bill_amount: "6000.00" }),
});
const DETAIL = {
    license_id: 2509, license_number: "3411008090", license_type: "DFIA", license_date: "2026-01-01", expiry_date: "2027-01-01",
    exporter_id: 1, exporter_name: "Exporter", port_id: 1, port_name: "Port", opening_balance: "0.00",
    license_running_balance: "100.00", closing_balance: "100.00",
    transactions: [txn(11, "PURCHASE"), txn(12, "SALE")],
    company_utilizations: { "1": { company_id: 1, company_name: "Acme", utilization_balance: "50.00" } },
    totals: { total_purchases: "100.00", total_sales: "50.00", total_commission: "0.00" },
};
const row = (trade_id: number, invoice_number: string, status: string) => ({
    trade_id, invoice_number, invoice_date: "2026-05-10", company_name: "Party", amount: "100", gst: null, total: "100", licence_amount: "100",
    settled: "50", outstanding: "50", status, payments: [], document: null,
});
const INVOICES = {
    purchase: { summary: { invoice_count: 1, total_amount: "100", total_settled: "50", total_outstanding: "50" }, rows: [row(11, "INV-11", "PARTIAL")] },
    sale: { summary: { invoice_count: 1, total_amount: "100", total_settled: "0", total_outstanding: "100" }, rows: [row(12, "INV-12", "UNPAID")] },
};
const BANK = {
    summary: { transaction_count: 1, total_payments: "50", total_receipts: "0", total_allocated: "50", total_unallocated: "0" },
    rows: [],
    trades: [
        { trade_id: 11, direction: "PURCHASE", invoice_number: "INV-11", invoice_date: null, total: "100", bank_settled: "50", outstanding: "50", status: "PARTIAL", linked: true,
          allocations: [{ payment_id: 1, date: "2026-06-01", bank_account: "HDFC", reference: "UTR-1", mode: "NEFT", bank_direction: "WITHDRAWAL", bank_amount: "50", allocated: "50", payment_unallocated: "0", invoice_number: "INV-11", reconciliation: "RECONCILED", status: "POSTED", counted: true }] },
        { trade_id: 12, direction: "SALE", invoice_number: "INV-12", invoice_date: null, total: "100", bank_settled: "0", outstanding: "100", status: "UNPAID", linked: false, allocations: [] },
    ],
};

function renderTab({ canSeeBank = true, canReadLicence = true } = {}) {
    getSpy.mockImplementation((url: string) => {
        if (url.startsWith("license-ledger/2509/ledger_detail/")) return Promise.resolve({ data: DETAIL });
        if (url === "licenses/2509/overview-payment-ledgers/") return Promise.resolve({ data: INVOICES });
        if (url === "accounting/licence-bank-ledger/2509/") return Promise.resolve({ data: BANK });
        return Promise.reject(new Error(`unexpected ${url}`));
    });
    const onOpenInvoice = vi.fn();
    const onOpenBank = vi.fn();
    render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
            <LedgerFinancialTab licenseId="2509" companyId="1" canSeeBank={canSeeBank} canReadLicence={canReadLicence} onOpenInvoice={onOpenInvoice} onOpenBank={onOpenBank} />
        </QueryClientProvider>,
    );
    return { onOpenInvoice, onOpenBank };
}

describe("Ledger tab — company-wise transactions with references only", () => {
    beforeEach(() => { getSpy.mockReset(); });

    it("links each transaction to its invoice and bank record instead of repeating them", async () => {
        const user = userEvent.setup();
        const { onOpenInvoice, onOpenBank } = renderTab();
        const purchase = await screen.findByRole("button", { name: "Open purchase invoice INV-11" });
        expect(purchase).toHaveTextContent("Partially paid");
        await user.click(purchase);
        expect(onOpenInvoice).toHaveBeenCalledWith("PURCHASE", "INV-11");
        await user.click(screen.getByRole("button", { name: "Open bank transaction UTR-1" }));
        expect(onOpenBank).toHaveBeenCalledWith("UTR-1");
        expect(screen.getByRole("button", { name: "Open sale invoice INV-12" })).toHaveTextContent("Not received");
        expect(screen.getByText("Bank: not linked")).toBeInTheDocument();
        // No duplicated invoice / bank tables and no repeated header or summary cards inside the tab.
        expect(screen.queryByRole("table", { name: /Bank transactions for invoice/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("table", { name: "Purchase ledger" })).not.toBeInTheDocument();
        expect(screen.queryByText(/TOTAL PURCHASE/i)).not.toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Bank movement summary" })).not.toBeInTheDocument();
    });

    it("without an accounting role: invoice links only, no bank link and no bank request", async () => {
        renderTab({ canSeeBank: false });
        expect(await screen.findByRole("button", { name: "Open purchase invoice INV-11" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Open bank transaction/ })).not.toBeInTheDocument();
        expect(getSpy).not.toHaveBeenCalledWith("accounting/licence-bank-ledger/2509/");
    });
});
