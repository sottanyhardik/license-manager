import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BoesTab from "./BoesTab";
import { fmtDate, fmtNum } from "./licenseOverviewHelpers";
import type { LicenseOverviewBoeRow } from "./types";

const hook = vi.hoisted(() => ({ data: [] as unknown[] }));
vi.mock("./useLicenseOverviewBoes", () => ({
    useLicenseOverviewBoes: () => ({ data: hook.data, isLoading: false, isError: false, error: null }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const STATUSES = ["Dispute", "Frozen", "Reconciled", "Pending"] as const;
const make = (n: number): LicenseOverviewBoeRow[] =>
    Array.from({ length: n }, (_, i) => ({
        bill_of_entry_number: `BOE${1000 + i}`,
        bill_of_entry_date: `2024-03-${String((i % 28) + 1).padStart(2, "0")}`,
        port: `PORT${i}`,
        supplier: `Supplier ${i}`,
        invoice_no: `INV-${i}`,
        invoice_date: `2024-02-${String((i % 28) + 1).padStart(2, "0")}`,
        cif_fc: 1234.5 + i,
        status: STATUSES[i % 4],
    }));

describe("BoesTab (always table, D3)", () => {
    beforeEach(() => {
        hook.data = [];
    });

    it.each([1, 3, 30])("renders a table carrying every old card field for %i records", (n) => {
        hook.data = make(n);
        render(<BoesTab licenseId={1} isActive />);
        expect(screen.getByRole("table")).toBeInTheDocument();
        const rows = screen.getAllByRole("row").slice(1);
        expect(rows).toHaveLength(n);
        for (const b of make(n)) {
            const row = rows.find((r) => within(r).queryByText(b.bill_of_entry_number!, { exact: false }));
            expect(row).toBeTruthy();
            const w = within(row!);
            // old card field list: number, copy action, status, supplier, date, port, invoice no, invoice date, CIF
            expect(w.getByText(b.supplier!)).toBeInTheDocument();
            expect(w.getByText(b.port!)).toBeInTheDocument();
            expect(w.getByText(b.invoice_no!)).toBeInTheDocument();
            expect(w.getByText(fmtDate(b.bill_of_entry_date))).toBeInTheDocument();
            expect(w.getByText(fmtDate(b.invoice_date))).toBeInTheDocument();
            expect(w.getByText(fmtNum(b.cif_fc))).toBeInTheDocument();
            expect(w.getByText(b.status)).toBeInTheDocument();
            expect(w.getByRole("button", { name: "Copy BOE number" })).toBeInTheDocument();
        }
    });

    it("keeps the copy action only for rows with a BOE number and no links", () => {
        hook.data = [{ ...make(1)[0], bill_of_entry_number: null }];
        render(<BoesTab licenseId={1} isActive />);
        expect(screen.queryByRole("button", { name: "Copy BOE number" })).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    it("leaves the existing client total untouched", () => {
        hook.data = make(3);
        render(<BoesTab licenseId={1} isActive />);
        expect(screen.getByText("Total CIF")).toBeInTheDocument();
        expect(screen.getByText(fmtNum(1234.5 + 1235.5 + 1236.5))).toBeInTheDocument();
    });
});
