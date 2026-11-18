import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LedgerFinancialTab from "./LedgerFinancialTab";

const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy } }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy } }));
vi.mock("react-router-dom", () => ({ useParams: () => ({}), useNavigate: () => vi.fn(), useLocation: () => ({ search: "", state: null }) }));
vi.mock("../../services/licenseLedgerExport", () => ({ previewLicenseLedgerPdf: vi.fn(), downloadLicenseLedgerExcel: vi.fn(), licenseLedgerExportError: (_e: unknown, f: string) => f }));

const txn = (id: number, type: "PURCHASE" | "SALE", party: string) => ({
    date: "2026-05-10", id, type, company_id: 1, company_name: "Acme", amount: "100.00", is_commission: false,
    affects_balance: true, license_running_balance: "100.00", company_utilization_after: "100.00", display_status: "Active",
    party_name: party, invoice_number: `INV-${id}`,
    ...(type === "PURCHASE" ? { purchase_amount: "100.00", purchase_bill_amount: "8000.00" } : { sale_amount: "50.00", sale_bill_amount: "6000.00" }),
});
const DETAIL = {
    license_id: 2509, license_number: "3411008090", license_type: "DFIA", license_date: "2026-01-01", expiry_date: "2027-01-01",
    exporter_id: 1, exporter_name: "Exporter", port_id: 1, port_name: "Port", opening_balance: "0.00",
    license_running_balance: "100.00", closing_balance: "100.00",
    transactions: [txn(11, "PURCHASE", "Supplier Co"), txn(12, "SALE", "Buyer Co")],
    company_utilizations: { "1": { company_id: 1, company_name: "Acme", utilization_balance: "50.00" } },
    totals: { total_purchases: "100.00", total_sales: "50.00", total_commission: "0.00" },
};
const BANK = {
    summary: {
        transaction_count: 2, total_payments: "4000.00", total_receipts: "0.00", total_allocated: "4000.00", total_unallocated: "0.00",
        total_withdrawals: "4000.00", total_credits: "0.00", total_allocated_payments: "4000.00", total_allocated_receipts: "0.00",
        total_unallocated_withdrawals: "0.00", total_unallocated_credits: "0.00", total_outstanding_purchase: "4000.00", total_outstanding_sales: "6000.00",
    },
    rows: [],
    trades: [
        {
            trade_id: 11, direction: "PURCHASE", invoice_number: "INV-11", invoice_date: "2026-05-10", total: "8000.00",
            bank_settled: "4000.00", outstanding: "4000.00", status: "PARTIAL", linked: true,
            allocations: [
                { payment_id: 1, date: "2026-06-01", bank_account: "HDFC 001", reference: "UTR-1", mode: "NEFT", bank_direction: "WITHDRAWAL",
                  bank_amount: "4000.00", allocated: "4000.00", payment_unallocated: "0.00", invoice_number: "INV-11", reconciliation: "RECONCILED", status: "POSTED", counted: true },
                { payment_id: 2, date: "2026-06-02", bank_account: "HDFC 001", reference: "UTR-DRAFT", mode: "NEFT", bank_direction: "WITHDRAWAL",
                  bank_amount: "1000.00", allocated: "1000.00", payment_unallocated: "0.00", invoice_number: "INV-11", reconciliation: "UNRECONCILED", status: "DRAFT", counted: false },
            ],
        },
        { trade_id: 12, direction: "SALE", invoice_number: "INV-12", invoice_date: "2026-05-11", total: "6000.00", bank_settled: "0.00", outstanding: "6000.00", status: "UNPAID", linked: false, allocations: [] },
    ],
};

function renderTab(canSeeBank: boolean, bank: () => Promise<unknown> = () => Promise.resolve({ data: BANK })) {
    getSpy.mockImplementation((url: string) => {
        if (url.startsWith("license-ledger/2509/ledger_detail/")) return Promise.resolve({ data: DETAIL });
        if (url === "accounting/licence-bank-ledger/2509/") return bank();
        return Promise.reject(new Error(`unexpected ${url}`));
    });
    return render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
            <LedgerFinancialTab licenseId="2509" companyId="1" canSeeBank={canSeeBank} />
        </QueryClientProvider>,
    );
}

describe("LedgerFinancialTab (financial view + bank details)", () => {
    beforeEach(() => { getSpy.mockReset(); });

    it("shows the licence-linked bank summary from the backend and per-transaction bank status with inline details", async () => {
        const user = userEvent.setup();
        renderTab(true);
        const summary = await screen.findByRole("region", { name: "Bank movement summary" });
        expect(summary).toHaveTextContent("licence-linked only");
        expect(within(summary).getByText("Total Bank Withdrawals").nextElementSibling).toHaveTextContent("₹4,000.00");
        expect(within(summary).getByText("Total Outstanding Sales Invoices").nextElementSibling).toHaveTextContent("₹6,000.00");

        // Purchase: partially paid → expand → real bank transactions (withdrawal), draft marked not counted.
        const purchaseToggle = await screen.findByRole("button", { name: "Bank details for invoice INV-11" });
        expect(purchaseToggle).toHaveTextContent("Partially paid");
        await user.click(purchaseToggle);
        const details = screen.getByRole("region", { name: "Bank details for invoice INV-11" });
        const table = within(details).getByRole("table", { name: "Bank transactions for invoice INV-11" });
        expect(within(table).getAllByText("WITHDRAWAL / DEBIT")).toHaveLength(2);
        expect(within(table).getByText("UTR-1")).toBeInTheDocument();
        expect(within(table).getByText("Reconciled")).toBeInTheDocument();
        expect(within(table).getByText("(draft, not counted)")).toBeInTheDocument();
        expect(details).toHaveTextContent("Outstanding ₹4,000.00");

        // Sale with no allocation: Not linked / Unallocated, never inferred.
        const saleToggle = screen.getByRole("button", { name: "Bank details for invoice INV-12" });
        expect(saleToggle).toHaveTextContent("Not linked");
        await user.click(saleToggle);
        expect(screen.getByText(/Not linked \/ Unallocated/)).toBeInTheDocument();
    });

    it("without an accounting role: the ledger renders, bank details are omitted and not requested", async () => {
        renderTab(false);
        expect(await screen.findByText("Bank payment and receipt details are shown to accounting roles.")).toBeInTheDocument();
        expect(getSpy).not.toHaveBeenCalledWith("accounting/licence-bank-ledger/2509/");
        expect(screen.queryByRole("button", { name: /Bank details for invoice/ })).not.toBeInTheDocument();
    });

    it("a 403 from the bank API is shown as the access note, not an error", async () => {
        renderTab(true, () => Promise.reject({ response: { status: 403 } }));
        expect(await screen.findByText("Bank payment and receipt details are shown to accounting roles.")).toBeInTheDocument();
    });
});
