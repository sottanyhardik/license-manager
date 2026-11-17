import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TransactionsTab from "./TransactionsTab";

const state = vi.hoisted(() => ({
    groups: { data: undefined as unknown, isLoading: false, isError: false, error: null as unknown },
    recordsParams: [] as unknown[],
    refetch: vi.fn(),
}));

vi.mock("./useLicenseOverviewTransactions", () => ({
    useLicenseOverviewTransactions: () => ({ ...state.groups, refetch: state.refetch, isFetching: false }),
    useLicenseOverviewTransactionRecords: (_id: unknown, params: unknown) => {
        state.recordsParams.push(params);
        return {
            data: {
                count: 1, total_pages: 1, current_page: 1, page_size: 25,
                results: [{
                    record_type: "BOE", line_id: 1, record_id: 1, record_number: "BOE-77", date: "2024-03-01",
                    qty: 10, cif_fc: 250, unit: "KG", status: "Reconciled", invoice_no: "INV-9", transaction_type: "D",
                }],
            },
            isLoading: false, isError: false, error: null, refetch: vi.fn(),
        };
    },
}));

const summary = (cif: number) => ({
    record_count_by_type: { BOE: 1, ALLOTMENT: 0 },
    line_count_by_type: { BOE: 1, ALLOTMENT: 0 },
    boe_buckets: [{ transaction_type: "D", record_count: 1, line_count: 1, cif_fc: cif, qty_by_unit: [{ unit: "KG", qty: 10, line_count: 1 }] }],
    allotment_buckets: [],
    boe_debit_cif: cif,
    unlinked_allotment_cif: 0,
    linked_allotment_cif: 0,
});

const groupsData = {
    count: 1, total_pages: 1, current_page: 1, page_size: 10,
    totals: summary(250),
    results: [{
        supplier_id: 5, supplier_name: "Acme", supplier_label: "Acme Traders", supplier_iec: "IEC1",
        is_missing_supplier: false, supplier_source: "company",
        summary: summary(250),
        products: [{
            product_key: 3, serial_number: 1, description: "d", unit: "KG", product_names: [],
            product_label: "Steel Coil", is_unmapped: false, summary: summary(250),
        }],
    }],
};

describe("TransactionsTab", () => {
    beforeEach(() => {
        state.groups = { data: groupsData, isLoading: false, isError: false, error: null };
        state.recordsParams = [];
        state.refetch.mockReset();
    });

    it("renders supplier groups with backend summaries", () => {
        render(<TransactionsTab licenseId={1} isActive />);
        expect(screen.getByText("Acme Traders")).toBeInTheDocument();
        expect(screen.getByText("Steel Coil")).toBeInTheDocument();
        expect(screen.getAllByText(/BOE Debit/).length).toBeGreaterThan(0);
        // Records are lazy: nothing requested until a row is expanded.
        expect(state.recordsParams).toHaveLength(0);
    });

    it("loads records only after expanding a product row", async () => {
        const user = userEvent.setup();
        render(<TransactionsTab licenseId={1} isActive />);
        expect(screen.queryByText("BOE-77")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /Expand/ }));
        expect(await screen.findByText("BOE-77")).toBeInTheDocument();
        expect(state.recordsParams[0]).toMatchObject({ supplier_id: 5, product_key: 3 });
    });

    it("shows the empty state", () => {
        state.groups = { data: { ...groupsData, count: 0, results: [] }, isLoading: false, isError: false, error: null };
        render(<TransactionsTab licenseId={1} isActive />);
        expect(screen.getByText(/No transactions found/)).toBeInTheDocument();
    });

    it("shows the error state and retries", async () => {
        const user = userEvent.setup();
        state.groups = { data: undefined, isLoading: false, isError: true, error: new Error("boom") };
        render(<TransactionsTab licenseId={1} isActive />);
        await user.click(screen.getByRole("button", { name: /Retry/ }));
        expect(state.refetch).toHaveBeenCalled();
    });
});
