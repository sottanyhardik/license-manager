import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ContextType, ReactNode } from "react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { openDocument } from "@/utils/documentDownload";
import LedgerLicenceWorkspace from "./LedgerLicenceWorkspace";
import { BankPaymentLedgerTab, PurchaseLedgerTab, SaleLedgerTab } from "./PaymentLedgers";
import type { BankLedger, BankLedgerRow, PaymentLedgers, TradeLedgerRow } from "./paymentLedgerApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("@/utils/documentDownload", () => ({ openDocument: vi.fn(async () => undefined) }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("../LicenseLedgerDetail", () => ({ default: () => <div>ledger detail</div> }));
vi.mock("../masters/MasterForm", () => ({ default: () => <div>master form</div> }));
vi.mock("@/features/licenses/tabs/BoeAllotmentTab", () => ({ default: () => <div>boe</div> }));
vi.mock("@/features/licenses/tabs/InvoicesTab", () => ({ default: () => <div>invoices</div> }));
vi.mock("@/features/licenses/tabs/HistoryTab", () => ({ default: () => <div>history</div> }));
vi.mock("@/components/workspace/LicenceCopiesSection", () => ({ LicenceCopiesSection: () => <div>copies</div> }));

const mockedGet = vi.mocked(api.get);
const mockedOpen = vi.mocked(openDocument);

function tradeRow(over: Partial<TradeLedgerRow> = {}): TradeLedgerRow {
    return {
        trade_id: 1, invoice_number: "PI-001", invoice_date: "2026-04-01", company_name: "Alpha Traders", amount: "1000.00", gst: null,
        total: "1000.00", licence_amount: "800.00", settled: "400.00", outstanding: "600.00", status: "PARTIAL",
        payments: [{ id: 9, date: "2026-04-05", amount: "400.00", note: "Part pay", bank_reference: "UTR123" }],
        document: { kind: "purchase_invoice_copy", url: "/media/pi.pdf" }, ...over,
    };
}
const section = (rows: TradeLedgerRow[]) => ({
    summary: { invoice_count: 77, total_amount: "123456.00", total_settled: "2345.00", total_outstanding: "99999.00" }, rows,
});
const trade = (purchase: TradeLedgerRow[], sale: TradeLedgerRow[] = []): PaymentLedgers => ({ purchase: section(purchase), sale: section(sale) });

function bankRow(over: Partial<BankLedgerRow> = {}): BankLedgerRow {
    return {
        payment_id: 5, date: "2026-04-06", bank_account: "HDFC 1234", reference: "UTR999", mode: "NEFT", direction: "PAYMENT", party: "Alpha Traders",
        amount: "500.00", status: "COMPLETED", allocated_to_licence: "300.00", unallocated: "200.00",
        invoices: [{ invoice_id: 1, number: "PI-001", trade_id: 1, amount: "300.00" }],
        reconciliation: "PARTIAL", statement_lines: [{ id: 3, txn_date: "2026-04-07", reference: "STMT-77", amount: "500.00" }], ...over,
    };
}
const bank = (rows: BankLedgerRow[]): BankLedger => ({
    summary: { transaction_count: 1, total_payments: "11111.00", total_receipts: "22222.00", total_allocated: "3333.00", total_unallocated: "444.00" }, rows,
});

function respond(map: Record<string, unknown | Error>) {
    mockedGet.mockImplementation(async (url: string) => {
        const hit = Object.entries(map).find(([k]) => url.includes(k));
        if (!hit) throw new Error(`unexpected ${url}`);
        if (hit[1] instanceof Error) throw hit[1];
        return { data: hit[1] };
    });
}
const forbidden = () => Object.assign(new Error("forbidden"), { response: { status: 403, data: { detail: "no" } } });

function wrap(ui: ReactNode, roles: string[] | "all" = "all") {
    const auth = { hasAnyRole: (r: readonly string[]) => roles === "all" || r.some((x) => roles.includes(x)) } as unknown as ContextType<typeof AuthContext>;
    return (
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
            <AuthContext.Provider value={auth}>{ui}</AuthContext.Provider>
        </QueryClientProvider>
    );
}
const workspace = (type = "DFIA") => <LedgerLicenceWorkspace licenseId="12" companyId="3" licenseNumber="0311" licenseType={type} />;

beforeEach(() => { mockedGet.mockReset(); mockedOpen.mockClear(); });

describe("continuous licence workspace (no tabs)", () => {
    const sectionLabels = () => Array.from(document.querySelectorAll<HTMLElement>("[data-testid=ledger-licence-workspace] section[aria-label]"))
        .map((el) => el.getAttribute("aria-label"));

    it("renders no tab navigation at all and keeps the required section order", () => {
        respond({ "ledger_detail": new Error("not needed"), "overview-payment-ledgers": trade([tradeRow()]), "licence-bank-ledger": bank([bankRow()]) });
        render(wrap(workspace()));
        expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
        expect(screen.queryAllByRole("tab")).toHaveLength(0);
        const order = sectionLabels().filter((l) => ["Purchase invoices", "Sale invoices", "Bank payment ledger", "Documents & licence copy"].includes(l ?? ""));
        expect(order).toEqual(["Purchase invoices", "Sale invoices", "Bank payment ledger", "Documents & licence copy"]);
        // Expandable sections replace the old BOE & Allotments / History tabs.
        expect(screen.getByRole("button", { name: "BOE & Allotments" })).toHaveAttribute("aria-expanded", "false");
        expect(screen.getByRole("button", { name: "Ownership History" })).toHaveAttribute("aria-expanded", "false");
        // Documents / Edit are inline actions.
        expect(screen.getByRole("button", { name: "Preview ledger PDF" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Edit licence" })).toHaveAttribute("aria-expanded", "false");
    });

    it("loads purchase and sale invoices on the page (no tab click needed)", async () => {
        respond({ "ledger_detail": new Error("not needed"), "overview-payment-ledgers": trade([tradeRow()], [tradeRow({ trade_id: 99, invoice_number: "S-99" })]), "licence-bank-ledger": bank([bankRow()]) });
        render(wrap(workspace()));
        expect(await screen.findByRole("table", { name: "Purchase ledger" })).toBeInTheDocument();
        expect(await screen.findByRole("table", { name: "Sale ledger" })).toBeInTheDocument();
        expect(mockedGet).toHaveBeenCalledWith("licenses/12/overview-payment-ledgers/");
    });

    it("hides the bank payment ledger without an accounting role", () => {
        respond({ "ledger_detail": new Error("not needed"), "overview-payment-ledgers": trade([tradeRow()]) });
        render(wrap(workspace(), ["LICENSE_VIEWER"]));
        const labels = sectionLabels();
        expect(labels).toContain("Purchase invoices");
        expect(labels).toContain("Sale invoices");
        expect(labels).not.toContain("Bank payment ledger");
        expect(mockedGet).not.toHaveBeenCalledWith("accounting/licence-bank-ledger/12/");
        expect(screen.queryByRole("button", { name: "Edit licence" })).not.toBeInTheDocument();
    });

    it("shows none of the DFIA-only sections for an incentive licence", () => {
        respond({ "ledger_detail": new Error("not needed") });
        render(wrap(workspace("INCENTIVE")));
        const labels = sectionLabels();
        for (const n of ["Purchase invoices", "Sale invoices", "Bank payment ledger"]) expect(labels).not.toContain(n);
        expect(screen.queryByRole("button", { name: "BOE & Allotments" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Customs ledger PDF" })).not.toBeInTheDocument();
    });
});

describe("purchase / sale ledgers", () => {
    it("renders rows, backend summary values and status badges", async () => {
        respond({ "overview-payment-ledgers": trade([
            tradeRow(),
            tradeRow({ trade_id: 2, invoice_number: "PI-002", status: "PAID", outstanding: "-50.00", settled: "1050.00" }),
            tradeRow({ trade_id: 3, invoice_number: "PI-003", status: "UNPAID", payments: [], document: null }),
        ]) });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        const table = await screen.findByRole("table", { name: "Purchase ledger" });
        expect(within(table).getByText("PI-001")).toBeInTheDocument();
        expect(within(table).getByText("Partially paid")).toBeInTheDocument();
        expect(within(table).getByText("Paid", { selector: "[data-slot=badge]" })).toBeInTheDocument();
        expect(within(table).getByText("Unpaid")).toBeInTheDocument();
        expect(within(table).getByText(/-₹50\.00/)).toBeInTheDocument();
        expect(within(table).getByText(/overpaid/)).toBeInTheDocument();
        expect(within(table).getAllByText("Not tracked")).toHaveLength(3);
        const summary = within(screen.getByLabelText("Purchase ledger summary"));
        expect(summary.getByText("Total Purchase Invoices").nextSibling).toHaveTextContent("77");
        expect(summary.getByText("Total Purchase Amount").nextSibling).toHaveTextContent("₹1,23,456.00");
        expect(summary.getByText("Total Paid").nextSibling).toHaveTextContent("₹2,345.00");
        expect(summary.getByText("Total Outstanding").nextSibling).toHaveTextContent("₹99,999.00");
    });

    it("sale tab shares the query and uses sale labels", async () => {
        respond({ "overview-payment-ledgers": trade([tradeRow()], [tradeRow({ trade_id: 8, invoice_number: "SI-008", company_name: "Beta Buyers", status: "UNPAID", document: { kind: "generated_sale_invoice", url: "/media/si.pdf" } })]) });
        render(wrap(<SaleLedgerTab licenseId={12} />));
        const table = await screen.findByRole("table", { name: "Sale ledger" });
        expect(within(table).getByText("SI-008")).toBeInTheDocument();
        expect(within(table).queryByText("PI-001")).not.toBeInTheDocument();
        expect(within(table).getByRole("columnheader", { name: "Customer" })).toBeInTheDocument();
        expect(within(table).getByRole("columnheader", { name: "Received" })).toBeInTheDocument();
        expect(within(screen.getByLabelText("Sale ledger summary")).getByText("Total Received")).toBeInTheDocument();
        expect(screen.getByRole("searchbox", { name: "Search sale ledger" })).toBeInTheDocument();
    });

    it("expands one row at a time and shows payments or the empty message", async () => {
        respond({ "overview-payment-ledgers": trade([tradeRow(), tradeRow({ trade_id: 3, invoice_number: "PI-003", payments: [] })]) });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        await screen.findByRole("table", { name: "Purchase ledger" });
        const first = screen.getByRole("button", { name: "Show payments for invoice PI-001" });
        expect(first).toHaveAttribute("aria-expanded", "false");
        await userEvent.click(first);
        expect(first).toHaveAttribute("aria-expanded", "true");
        const payments = screen.getByRole("table", { name: "Payments for invoice PI-001" });
        expect(within(payments).getByText("UTR123")).toBeInTheDocument();
        expect(within(payments).getByText("Part pay")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "Show payments for invoice PI-003" }));
        expect(first).toHaveAttribute("aria-expanded", "false");
        expect(screen.getByText("No payments recorded")).toBeInTheDocument();
    });

    it("searches by invoice number and company", async () => {
        respond({ "overview-payment-ledgers": trade([tradeRow(), tradeRow({ trade_id: 2, invoice_number: "PI-002", company_name: "Gamma Co" })]) });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        const table = await screen.findByRole("table", { name: "Purchase ledger" });
        const box = screen.getByRole("searchbox", { name: "Search purchase ledger" });
        await userEvent.type(box, "gamma");
        expect(within(table).queryByText("PI-001")).not.toBeInTheDocument();
        expect(within(table).getByText("PI-002")).toBeInTheDocument();
        await userEvent.clear(box);
        await userEvent.type(box, "PI-001");
        expect(within(table).getByText("PI-001")).toBeInTheDocument();
        expect(within(table).queryByText("PI-002")).not.toBeInTheDocument();
    });

    it("paginates 25 per page and resets the page on search", async () => {
        const rows = Array.from({ length: 30 }, (_, i) => tradeRow({ trade_id: i + 1, invoice_number: `INV-${String(i + 1).padStart(3, "0")}` }));
        respond({ "overview-payment-ledgers": trade(rows) });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        const table = await screen.findByRole("table", { name: "Purchase ledger" });
        expect(screen.getByText("1–25 of 30")).toBeInTheDocument();
        expect(within(table).queryByText("INV-030")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();
        await userEvent.click(screen.getByRole("button", { name: "Next" }));
        expect(screen.getByText("26–30 of 30")).toBeInTheDocument();
        expect(within(table).getByText("INV-030")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
        await userEvent.type(screen.getByRole("searchbox", { name: "Search purchase ledger" }), "INV-02");
        expect(screen.getByText("1–10 of 10")).toBeInTheDocument();
    });

    it("opens the invoice through openDocument", async () => {
        respond({ "overview-payment-ledgers": trade([tradeRow()]) });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        await screen.findByRole("table", { name: "Purchase ledger" });
        await userEvent.click(screen.getByRole("button", { name: "Open invoice PI-001" }));
        expect(mockedOpen).toHaveBeenCalledWith("/media/pi.pdf", "PI-001.pdf");
    });

    it("shows the empty state, the no-access state and a retryable error", async () => {
        respond({ "overview-payment-ledgers": trade([]) });
        const first = render(wrap(<PurchaseLedgerTab licenseId={12} />));
        expect(await screen.findByText("No purchase invoices for this licence")).toBeInTheDocument();
        first.unmount();

        respond({ "overview-payment-ledgers": forbidden() });
        const second = render(wrap(<PurchaseLedgerTab licenseId={12} />));
        expect(await screen.findByText("You don't have access to these invoices")).toBeInTheDocument();
        second.unmount();

        respond({ "overview-payment-ledgers": new Error("boom") });
        render(wrap(<PurchaseLedgerTab licenseId={12} />));
        const retry = await screen.findByRole("button", { name: "Retry" });
        respond({ "overview-payment-ledgers": trade([tradeRow()]) });
        await userEvent.click(retry);
        expect(await screen.findByRole("table", { name: "Purchase ledger" })).toBeInTheDocument();
    });
});

describe("bank payment ledger", () => {
    it("renders one row per payment with badges, summary and expansion", async () => {
        respond({ "accounting/licence-bank-ledger/12/": bank([
            bankRow(),
            bankRow({ payment_id: 6, reference: "UTR-R", direction: "RECEIPT", reconciliation: "RECONCILED", invoices: [], statement_lines: [] }),
            bankRow({ payment_id: 7, reference: "UTR-U", reconciliation: "UNRECONCILED" }),
        ]) });
        render(wrap(<BankPaymentLedgerTab licenseId={12} />));
        const table = await screen.findByRole("table", { name: "Bank payment ledger" });
        expect(within(table).getAllByRole("row")).toHaveLength(4);
        expect(within(table).getByText("Reconciled")).toBeInTheDocument();
        expect(within(table).getByText("Partially reconciled")).toBeInTheDocument();
        expect(within(table).getByText("Unreconciled")).toBeInTheDocument();
        expect(within(table).getByText("Receipt")).toBeInTheDocument();
        const summary = within(screen.getByLabelText("Bank payment ledger summary"));
        expect(summary.getByText("Total Payments").nextSibling).toHaveTextContent("₹11,111.00");
        expect(summary.getByText("Total Receipts").nextSibling).toHaveTextContent("₹22,222.00");
        expect(summary.getByText("Total Allocated")).toBeInTheDocument();
        expect(summary.getByText("Total Unallocated")).toBeInTheDocument();

        await userEvent.click(screen.getByRole("button", { name: "Show allocations for UTR999" }));
        const invoices = screen.getByRole("table", { name: "Invoice allocations for UTR999" });
        expect(within(invoices).getByText("PI-001")).toBeInTheDocument();
        const lines = screen.getByRole("table", { name: "Statement lines for UTR999" });
        expect(within(lines).getByText("STMT-77")).toBeInTheDocument();

        await userEvent.type(screen.getByRole("searchbox", { name: "Search bank payment ledger" }), "UTR-U");
        await waitFor(() => expect(within(table).queryByText("UTR-R")).not.toBeInTheDocument());
    });

    it("renders a no-access state on 403 and a retry on other errors", async () => {
        respond({ "accounting/licence-bank-ledger": forbidden() });
        const first = render(wrap(<BankPaymentLedgerTab licenseId={12} />));
        expect(await screen.findByText("You don't have access to bank transactions")).toBeInTheDocument();
        first.unmount();

        respond({ "accounting/licence-bank-ledger": new Error("boom") });
        render(wrap(<BankPaymentLedgerTab licenseId={12} />));
        expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    });
});
