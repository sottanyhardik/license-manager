import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { InvoiceActivity as InvoiceActivityData } from "@/pages/dashboardContract";
import { v3Fixture } from "./fixtures";
import InvoiceActivity from "./InvoiceActivity";

const invoiceSection = v3Fixture.invoice_activity as InvoiceActivityData;

function renderInvoices(section: InvoiceActivityData | { error: string } | undefined, props: { onRetry?: () => void; retrying?: boolean; search?: string } = {}) {
    return render(
        <MemoryRouter>
            <InvoiceActivity section={section} search={props.search ?? ""} onRetry={props.onRetry} retrying={props.retrying} />
        </MemoryRouter>,
    );
}

function invoiceRow(number: string, status: InvoiceActivityData["recent"][number]["status"]): InvoiceActivityData["recent"][number] {
    return {
        id: number.length,
        invoice_number: number,
        invoice_date: "2026-10-28",
        direction: "sale",
        party_name: `Customer for ${number}`,
        total_amount_inr: "1000.00",
        outstanding_inr: status === "paid" ? "0.00" : "1000.00",
        status,
    };
}

describe("InvoiceActivity", () => {
    it("renders the recent invoices with number, date, customer, amount, outstanding and status", () => {
        renderInvoices(invoiceSection);

        const table = screen.getByRole("table", { name: "Recent invoices with outstanding amounts" });
        const first = invoiceSection.recent[0]!;
        expect(within(table).getByText(first.invoice_number)).toBeInTheDocument();
        expect(within(table).getByText(first.party_name!)).toBeInTheDocument();
    });

    it("shows the status counts and the outstanding total from the section", () => {
        renderInvoices(invoiceSection);

        expect(screen.getByText("Total invoices")).toBeInTheDocument();
        expect(screen.getByText("Outstanding (₹)", { exact: false })).toBeInTheDocument();
    });

    it("renders each settlement status with its own label", () => {
        const section: InvoiceActivityData = {
            ...invoiceSection,
            recent: [
                invoiceRow("INV-PAID", "paid"),
                invoiceRow("INV-PART", "partially_paid"),
                invoiceRow("INV-OPEN", "unpaid"),
            ],
        };
        renderInvoices(section);

        const table = screen.getByRole("table", { name: "Recent invoices with outstanding amounts" });
        expect(within(table).getByText("Paid")).toBeInTheDocument();
        expect(within(table).getByText("Partially paid")).toBeInTheDocument();
        expect(within(table).getByText("Unpaid")).toBeInTheDocument();
    });

    it("renders the empty state for a valid empty list, not an error", () => {
        renderInvoices({ ...invoiceSection, total: 0, recent: [] });

        expect(screen.getByText("No recent invoices")).toBeInTheDocument();
        expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument();
    });

    it("says which states are not tracked, so an absent Draft or Posted count is not mistaken for zero", () => {
        renderInvoices(invoiceSection);

        expect(screen.getByText(/Not tracked in this system: Draft, Pending, Confirmed, Posted/)).toBeInTheDocument();
    });

    it("shows the section error with a Retry action that calls onRetry", () => {
        const onRetry = vi.fn();
        renderInvoices({ error: "Dashboard section 'invoice_activity' could not be loaded" }, { onRetry });

        expect(screen.getByText(/could not be loaded/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry Invoice activity" }));
        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it("shows the loading skeleton while a retry is in flight, not the old error", () => {
        renderInvoices({ error: "Could not load" }, { onRetry: vi.fn(), retrying: true });

        expect(screen.getByTestId("section-skeleton")).toBeInTheDocument();
        expect(screen.queryByText(/Could not load/)).not.toBeInTheDocument();
    });

    it("renders nothing when the section is absent because the role does not grant it", () => {
        const { container } = renderInvoices(undefined);

        expect(container).toBeEmptyDOMElement();
    });

    it("filters the visible rows by invoice number or customer, using the page search", () => {
        const section: InvoiceActivityData = {
            ...invoiceSection,
            recent: [invoiceRow("INV-ALPHA", "unpaid"), invoiceRow("INV-BETA", "paid")],
        };
        renderInvoices(section, { search: "beta" });

        const table = screen.getByRole("table", { name: "Recent invoices with outstanding amounts" });
        expect(within(table).getByText("INV-BETA")).toBeInTheDocument();
        expect(within(table).queryByText("INV-ALPHA")).not.toBeInTheDocument();
    });
});
