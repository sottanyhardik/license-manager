import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } }));
vi.mock("./axios", () => ({ default: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } }));

import AccountingWorkspace from "./AccountingWorkspace";

const BOOKS = { id: 7, company_id: 7, name: "Labdhi Mercantile LLP", gstin: "27AAAFL0000A1Z5", pan: null, state_code: "27",
    books_start_date: "2026-04-01", default_credit_days: 0, require_maker_checker: false, is_active: true };

function respond(url: string) {
    if (url === "accounting/entities/") return { data: { books: [BOOKS], discovered: [] } };
    if (url === "accounting/reports/dashboard/") {
        return { data: { sales: "1160000.00", purchases: "1000000.00", gross_profit: "160000.00", net_profit: "-2500.50",
            bank_balance: "548200.00", cash_balance: "0.00", receivables: "0.00", payables: "0.00", overdue_receivables: "0.00",
            overdue_payables: "0.00", draft_vouchers: 1, unposted_invoices: 2, unmatched_bank_lines: 3, open_suspense: 0,
            gst_net_payable: "0.00", tds_payable: "20000.00", loan_outstanding: "0.00" } };
    }
    if (url === "accounting/trades/") {
        return { data: { count: 1, page: 1, page_size: 50, next: null, previous: null, summary: { NOT_ACCOUNTED: 1 },
            results: [{ trade_id: 11, direction: "PURCHASE", invoice_number: "LML/2026-27/0001", invoice_date: "2026-05-01",
                party: "Exporter Pvt Ltd", trade_total: "1000000.00", accounting_status: "NOT_ACCOUNTED", invoice_id: null,
                invoice_status: null, voucher_id: null, voucher_number: null, payment_status: null, outstanding: null,
                trade_payments: 0, unaccounted_payment_ids: [], is_paired: false }] } };
    }
    if (url === "accounting/bank-accounts/") return { data: [] };
    return { data: {} };
}

function renderAt(path: string) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={qc}>
            <MemoryRouter initialEntries={[path]}>
                <Routes><Route path="/accounting/*" element={<AccountingWorkspace />} /></Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

describe("AccountingWorkspace", () => {
    beforeEach(() => {
        get.mockReset();
        post.mockReset();
        get.mockImplementation((url: string) => Promise.resolve(respond(url)));
    });

    it("shows entity-scoped dashboard figures formatted from Decimal strings", async () => {
        renderAt("/accounting/dashboard");
        expect(await screen.findByText("₹ 11,60,000.00")).toBeInTheDocument();
        expect(screen.getByText("₹ -2,500.50")).toBeInTheDocument();
        expect(screen.getByRole("combobox", { name: "Entity" })).toHaveValue("7");
        expect(get).toHaveBeenCalledWith("accounting/reports/dashboard/", expect.objectContaining({ params: expect.objectContaining({ entity: 7 }) }));
    });

    it("lists trades with their accounting status and a post action", async () => {
        renderAt("/accounting/trades");
        const row = (await screen.findByText("LML/2026-27/0001")).closest("tr")!;
        expect(within(row).getByText("NOT ACCOUNTED")).toBeInTheDocument();
        expect(within(row).getByText("10,00,000.00")).toBeInTheDocument();
        expect(within(row).getByRole("button", { name: "Post to books" })).toBeEnabled();
    });

    it("asks for confirmation before posting a trade and only posts after confirming", async () => {
        post.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith("from-trade/") ? { id: 99 } : {} }));
        renderAt("/accounting/trades");
        const row = (await screen.findByText("LML/2026-27/0001")).closest("tr")!;
        within(row).getByRole("button", { name: "Post to books" }).click();
        const dialog = await screen.findByRole("alertdialog");
        expect(within(dialog).getByText(/10,00,000\.00/)).toBeInTheDocument();
        expect(post).not.toHaveBeenCalled();
        within(dialog).getByRole("button", { name: "Post" }).click();
        await waitFor(() => expect(post).toHaveBeenCalledWith("accounting/invoices/99/post/", {}));
        expect(post).toHaveBeenCalledWith("accounting/invoices/from-trade/", { trade_id: 11 });
    });
});
