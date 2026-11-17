import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            if (url === "bill-of-entries/") return Promise.resolve({ data: LIST_RESPONSE });
            return new Promise(() => {});
        }),
        post: vi.fn(() => new Promise(() => {})),
        patch: vi.fn(() => new Promise(() => {})),
        put: vi.fn(() => new Promise(() => {})),
        delete: vi.fn(() => new Promise(() => {})),
    },
}));

import { BOE_FIXTURE, LIST_RESPONSE, boeCards, renderBoeList, type Role } from "./fixtures";

async function ready() {
    await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
}

describe("BOE register table", () => {
    beforeEach(() => vi.clearAllMocks());
    afterEach(() => cleanup());

    it("renders the compact columns with backend values, links and a dispute indicator", async () => {
        renderBoeList("BOE_MANAGER");
        await ready();
        const headers = screen.getAllByRole("columnheader").map((h) => h.textContent?.trim());
        expect(headers).toEqual(expect.arrayContaining(["BOE Number", "BOE Date", "Port", "Product", "Invoice No", "CIF (INR)", "CIF (FC)", "Qty", "Unit Price", "Licence(s)", "Invoice"]));

        const row = boeCards()[0];
        expect(within(row).getByRole("link", { name: "7012345" })).toHaveAttribute("href", "/bill-of-entries/201");
        expect(within(row).getByRole("link", { name: "0310123456" })).toHaveAttribute("href", "/licenses/11/overview");
        expect(within(row).getByText("Invoiced")).toBeInTheDocument();
        expect(within(row).getByText("₹12,34,568")).toBeInTheDocument();
        expect(within(row).getByText("15,000.5")).toBeInTheDocument();
        expect(within(boeCards()[1]).getByText("1 Dispute")).toBeInTheDocument();
        expect(within(boeCards()[1]).getByText("Not invoiced")).toBeInTheDocument();
        expect(within(boeCards()[0]).queryByText(/Dispute/)).toBeNull();
    });

    it("renders the status badge from invoice_status, not from invoice_no", async () => {
        renderBoeList("BOE_MANAGER");
        await ready();
        // 204 has an invoice_no but is only "Invoice no. recorded"; never "Invoiced".
        const rec = within(boeCards()[3]);
        expect(rec.getByText("Invoice no. recorded")).toBeInTheDocument();
        expect(rec.queryByText("Invoiced")).toBeNull();
        expect(rec.getByText("Invoice no. recorded").closest("[data-tone]")).toHaveAttribute("data-tone", "info");
        expect(within(boeCards()[0]).getByText("Invoiced").closest("[data-tone]")).toHaveAttribute("data-tone", "success");
    });

    const invoiceGate: Array<[Role, boolean, boolean]> = [
        ["BOE_MANAGER", true, true],
        ["BOE_VIEWER", true, false],
        ["ACCOUNT_ACCESS", true, false],
    ];
    for (const [role, canInvoice, canMenu] of invoiceGate) {
        it(`gates invoice edit and the actions menu (${role})`, async () => {
            renderBoeList(role);
            await ready();
            expect(!!within(boeCards()[0]).queryByTitle("Click to edit invoice number")).toBe(canInvoice);
            expect(!!within(boeCards()[0]).queryByRole("button", { name: "Actions for BOE 7012345" })).toBe(canMenu);
        });
    }

    it("edits the invoice number inline and cancels on Escape", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await ready();
        await user.click(within(boeCards()[1]).getByRole("button", { name: /Add Invoice No/ }));
        const input = screen.getByRole("textbox", { name: "Invoice number" });
        await user.type(input, "INV-9");
        expect(input).toHaveValue("INV-9");
        expect(screen.getByRole("textbox", { name: "Invoice number" })).toBe(input);
        await user.keyboard("{Escape}");
        expect(screen.queryByRole("textbox", { name: "Invoice number" })).toBeNull();
    });
});
