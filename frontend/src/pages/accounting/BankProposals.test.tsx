import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), delete: (...a: unknown[]) => del(...a) } }));

import { AuthContext } from "@/context/AuthContext";
import type { AuthContextValue } from "@/types";

import AccountingWorkspace from "./AccountingWorkspace";

const BOOKS = { id: 7, company_id: 7, name: "Labdhi Mercantile LLP", gstin: "27AAAFL0000A1Z5", pan: null, state_code: "27",
    books_start_date: "2026-04-01", default_credit_days: 0, require_maker_checker: false, is_active: true };
const BANK = { id: 3, account_id: 30, bank_name: "HDFC", account_number: "1234", ifsc: "", is_cash: false, book_balance: "0.00" };

const mk = (id: number, over: Record<string, unknown> = {}) => ({
    line: { id, txn_date: "2026-05-02", narration: `NEFT ACME ${id}`, reference: "", debit: "0.00", credit: "1180.50", amount: "1180.50", status: "UNMATCHED" },
    direction: "RECEIPT", counterparty: "ACME", party: { id: 100 + id, name: `Acme ${id}`, gstin: null }, source: "alias", score: 100,
    confidence: "high", blocked: null, options: [{ id: 555, name: "Other Co", gstin: null, score: 60 }],
    allocations: [{ invoice_id: 9, number: `INV-${id}`, date: "2026-04-01", due_date: null, outstanding: "1000.00", amount: "1000.00" }],
    advance: "180.50", exact_bill: false, existing_candidates: 0, ...over,
});
const HIGH = mk(1);
const LOW = mk(2, { confidence: "low", party: null, source: "", allocations: [], advance: "0.00" });

function respond(url: string, config?: { params?: Record<string, unknown> }) {
    if (url === "accounting/entities/") return { data: { books: [BOOKS], discovered: [] } };
    if (url === "accounting/bank-accounts/") return { data: [BANK] };
    if (url === "accounting/bank-accounts/3/proposals/") {
        const wantsLow = String(config?.params?.confidence ?? "").includes("low");
        return { data: { bank_account_id: 3, summary: { high: 1, medium: 0, low: 1, none: 0, total: 2 },
            proposals: wantsLow ? [HIGH, LOW] : [HIGH] } };
    }
    if (url === "accounting/statement-lines/1/proposal/") return { data: mk(1, { party: { id: 555, name: "Other Co", gstin: null }, source: "chosen" }) };
    if (url === "accounting/narration-aliases/") return { data: { aliases: [] } };
    return { data: {} };
}

function authAs(roles: string[]): AuthContextValue {
    const has = (codes: readonly string[]) => codes.some((r) => roles.includes(r));
    return { user: null, hasRole: (r: string) => roles.includes(r), hasAnyRole: has, isSuperAdmin: () => false } as unknown as AuthContextValue;
}

function renderAt(roles: string[] = ["ACCOUNTS_APPROVER"]) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <AuthContext.Provider value={authAs(roles)}>
            <QueryClientProvider client={qc}>
                <MemoryRouter initialEntries={["/accounting/banking/proposals"]}>
                    <Routes><Route path="/accounting/*" element={<AccountingWorkspace />} /></Routes>
                </MemoryRouter>
            </QueryClientProvider>
        </AuthContext.Provider>,
    );
}

describe("BankProposals", () => {
    beforeEach(() => {
        get.mockReset(); post.mockReset(); del.mockReset();
        get.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => Promise.resolve(respond(url, config)));
    });

    it("renders proposals with the summary chips and formatted amounts", async () => {
        renderAt();
        const row = (await screen.findByText("NEFT ACME 1")).closest("tr")!;
        expect(within(row).getByText("Acme 1")).toBeInTheDocument();
        expect(within(row).getByText("learned")).toBeInTheDocument();
        expect(within(row).getByText("1,180.50")).toBeInTheDocument();
        expect(within(row).getByText(/INV-1/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^High 1/ })).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByRole("button", { name: /^Low 1/ })).toHaveAttribute("aria-pressed", "false");
    });

    it("refetches with the chosen confidence filter", async () => {
        renderAt();
        await screen.findByText("NEFT ACME 1");
        await userEvent.click(screen.getByRole("button", { name: /^Low/ }));
        expect(await screen.findByText("NEFT ACME 2")).toBeInTheDocument();
        expect(get).toHaveBeenCalledWith("accounting/bank-accounts/3/proposals/",
            expect.objectContaining({ params: expect.objectContaining({ confidence: "high,medium,low" }) }));
    });

    it("previews a party override and confirms the selected {line_id, party_id}", async () => {
        post.mockResolvedValue({ data: { confirmed: [{ line_id: 1, payment_id: 5, voucher: "RV-1" }], errors: [] } });
        renderAt();
        const row = (await screen.findByText("NEFT ACME 1")).closest("tr")!;
        await userEvent.selectOptions(within(row).getByRole("combobox", { name: "Suggested parties for line 1" }), "555");
        await waitFor(() => expect(get).toHaveBeenCalledWith("accounting/statement-lines/1/proposal/", expect.objectContaining({ params: { party_id: 555 } })));
        expect(await within(row).findByText("Other Co", { selector: "span, div, p, b, strong" })).toBeInTheDocument();
        expect(within(row).queryByText(/^chosen$/i)).not.toBeInTheDocument();
        await userEvent.click(screen.getByRole("checkbox", { name: "Select line 1" }));
        await userEvent.click(screen.getByRole("button", { name: "Confirm selected (1)" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toHaveTextContent(/1 receipt .*0 payments.*1,180\.50/);
        await userEvent.click(within(dialog).getByRole("button", { name: "Post" }));
        await waitFor(() => expect(post).toHaveBeenCalledWith("accounting/bank-accounts/3/proposals/confirm/", { items: [{ line_id: 1, party_id: 555 }] }));
        expect(await screen.findByText("1 line confirmed")).toBeInTheDocument();
    });

    it("hides confirm and selection for a viewer", async () => {
        renderAt(["ACCOUNTS_VIEWER"]);
        await screen.findByText("NEFT ACME 1");
        expect(screen.queryByRole("button", { name: /Confirm selected/ })).toBeNull();
        expect(screen.queryByRole("checkbox")).toBeNull();
        expect(screen.getByRole("note")).toHaveTextContent("Read-only");
    });
});
