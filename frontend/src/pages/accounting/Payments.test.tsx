import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } }));

import { AuthContext } from "@/context/AuthContext";
import type { AuthContextValue } from "@/types";

import AccountingWorkspace from "./AccountingWorkspace";

const BOOKS = { id: 7, company_id: 7, name: "Labdhi Mercantile LLP", gstin: "27AAAFL0000A1Z5", pan: null, state_code: "27",
    books_start_date: "2026-04-01", default_credit_days: 0, require_maker_checker: false, is_active: true };
const BANK = { id: 3, account_id: 30, bank_name: "HDFC", account_number: "1234", ifsc: "", is_cash: false, book_balance: "0.00" };
const PARTY = { id: 41, name: "Supersonic Distribution", gstin: "27AAACS9511P1ZV", pan: null };
const bill = (id: number, number: string, outstanding: string, date: string) => ({
    id, kind: "SALES", number, party_id: 41, party: PARTY.name, party_reference: "", date, due_date: date,
    outstanding, payment_status: "OVERDUE", status: "POSTED",
});
const BILLS = [bill(30, "LML/0030", "494032.00", "2026-10-23"), bill(27, "LML/0027", "526019.00", "2026-10-09")];
const LINE = { id: 88, bank_account_id: 3, bank: "HDFC 1234", txn_date: "2026-11-02", narration: "RTGS SUPERSONIC DISTRIBUTION AND",
    reference: "UTIBR52026110200001", amount: "1020051.00", remaining: "1020051.00", status: "UNMATCHED", mode: "RTGS", score: 1, source: "name" };

function respond(url: string) {
    if (url === "accounting/entities/") return { data: { books: [BOOKS], discovered: [] } };
    if (url === "accounting/bank-accounts/") return { data: [BANK] };
    if (url === "accounting/parties/") return { data: [PARTY] };
    if (url === "accounting/invoices/") return { data: { count: 2, next: null, previous: null, results: BILLS } };
    if (url === "accounting/parties/41/bank-lines/") return { data: { lines: [LINE] } };
    if (url === "accounting/payments/") return { data: { count: 0, next: null, previous: null, results: [] } };
    return { data: {} };
}

function authAs(roles: string[]): AuthContextValue {
    const has = (codes: readonly string[]) => codes.some((r) => roles.includes(r));
    return { user: null, hasRole: (r: string) => roles.includes(r), hasAnyRole: has, isSuperAdmin: () => false } as unknown as AuthContextValue;
}

async function openForm() {
    const user = userEvent.setup();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
        <AuthContext.Provider value={authAs(["ACCOUNTS_APPROVER"])}>
            <QueryClientProvider client={qc}>
                <MemoryRouter initialEntries={["/accounting/payments"]}>
                    <Routes><Route path="/accounting/*" element={<AccountingWorkspace />} /></Routes>
                </MemoryRouter>
            </QueryClientProvider>
        </AuthContext.Provider>,
    );
    await user.click(await screen.findByRole("radio", { name: "Receive from customer" }));
    await user.type(screen.getByRole("combobox", { name: "Party" }), "Supe");
    await user.click(await screen.findByRole("option", { name: /Supersonic Distribution/ }));
    await screen.findByText("LML/0030");
    return user;
}

async function postAndConfirm(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: "Post receipt" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: /^Post$/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    return post.mock.calls[0][1] as Record<string, unknown>;
}

describe("Record payment / receipt", () => {
    beforeEach(() => {
        get.mockReset(); post.mockReset();
        get.mockImplementation((url: string) => Promise.resolve(respond(url)));
        post.mockResolvedValue({ data: { id: 1, voucher_number: "RCT/0001" } });
    });

    it("ticking invoices settles them in full and fills the amount", async () => {
        const user = await openForm();
        await user.selectOptions(screen.getByRole("combobox", { name: /Bank \/ cash/ }), "3");
        await user.click(screen.getByRole("checkbox", { name: "Settle LML/0030" }));
        await user.click(screen.getByRole("checkbox", { name: "Settle LML/0027" }));
        expect(screen.getByRole("textbox", { name: "Allocate to LML/0027" })).toHaveValue("526019.00");
        expect(screen.getByDisplayValue("1020051.00")).toBeInTheDocument();
        const body = await postAndConfirm(user);
        expect(body.amount).toBe("1020051.00");
        expect(body.allocations).toEqual([{ invoice_id: 27, amount: "526019.00" }, { invoice_id: 30, amount: "494032.00" }]);
        expect(body).not.toHaveProperty("statement_line_id");
    });

    it("on account sends no bill allocations", async () => {
        const user = await openForm();
        await user.selectOptions(screen.getByRole("combobox", { name: /Bank \/ cash/ }), "3");
        await user.click(screen.getByRole("checkbox", { name: "Settle LML/0030" }));
        await user.click(screen.getByRole("radio", { name: "On account (advance)" }));
        expect(screen.queryByText("LML/0030")).not.toBeInTheDocument();
        const body = await postAndConfirm(user);
        expect(body.allocations).toEqual([]);
        expect(body.amount).toBe("494032.00");
    });

    it("picking a bank transaction fills bank, date, amount and UTR and is sent for matching", async () => {
        const user = await openForm();
        await user.click(screen.getByRole("button", { name: "Pick bank transaction" }));
        await user.click(await screen.findByRole("button", { name: /Use bank transaction of 2026-11-02/ }));
        expect(screen.getByRole("status")).toHaveTextContent("RTGS SUPERSONIC DISTRIBUTION AND");
        expect(screen.getByDisplayValue("UTIBR52026110200001")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Allocate oldest first" }));
        const body = await postAndConfirm(user);
        expect(body).toMatchObject({ statement_line_id: 88, bank_account_id: "3", date: "2026-11-02", amount: "1020051.00",
            mode: "RTGS", reference: "UTIBR52026110200001", direction: "RECEIPT", party_id: 41 });
        expect(body.allocations).toEqual([{ invoice_id: 27, amount: "526019.00" }, { invoice_id: 30, amount: "494032.00" }]);
    });

    it("refuses an amount above the bank transaction's unmatched amount", async () => {
        const user = await openForm();
        await user.click(screen.getByRole("button", { name: "Pick bank transaction" }));
        await user.click(await screen.findByRole("button", { name: /Use bank transaction/ }));
        const amount = screen.getByDisplayValue("1020051.00");
        await user.clear(amount);
        await user.type(amount, "1020052.00");
        expect(screen.getByRole("alert")).toHaveTextContent("more than the bank transaction's unmatched");
        expect(screen.getByRole("button", { name: "Post receipt" })).toBeDisabled();
    });
});
