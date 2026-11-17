import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AllotmentsTab from "./AllotmentsTab";
import { fmtDate, fmtNum } from "./licenseOverviewHelpers";
import type { LicenseOverviewAllotmentRow } from "./types";

const hook = vi.hoisted(() => ({ data: [] as unknown[] }));
vi.mock("./useLicenseOverviewAllotments", () => ({
    useLicenseOverviewAllotments: () => ({ data: hook.data, isLoading: false, isError: false, error: null }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const STATUSES = ["Linked to BOE", "Approved", "Allotted", "Pending"] as const;
const make = (n: number): LicenseOverviewAllotmentRow[] =>
    Array.from({ length: n }, (_, i) => ({
        allotment_number: `ALT-${100 + i}`,
        date: `2024-04-${String((i % 28) + 1).padStart(2, "0")}`,
        customer: `Customer ${i}`,
        product: `Product ${i}`,
        quantity: 100 + i,
        cif_fc: 5000 + i * 10,
        // Engine semantics: a BOE-linked allotment has no outstanding CIF.
        outstanding_cif_fc: STATUSES[i % 4] === "Linked to BOE" ? 0 : 5000 + i * 10,
        status: STATUSES[i % 4],
    }));

describe("AllotmentsTab (always table, D3)", () => {
    beforeEach(() => {
        hook.data = [];
    });

    it.each([1, 3, 30])("renders a table carrying every old card field for %i records", (n) => {
        hook.data = make(n);
        render(<AllotmentsTab licenseId={1} isActive />);
        expect(screen.getByRole("table")).toBeInTheDocument();
        const rows = screen.getAllByRole("row").slice(1);
        expect(rows).toHaveLength(n);
        for (const a of make(n)) {
            const row = rows.find((r) => within(r).queryByText(a.allotment_number, { exact: false }) && within(r).queryByText(a.customer!));
            expect(row).toBeTruthy();
            const w = within(row!);
            // old card field list: number, copy action, status, customer, product, date, qty, rate, CIF
            expect(w.getByText(a.customer!)).toBeInTheDocument();
            expect(w.getByText(a.product!)).toBeInTheDocument();
            expect(w.getByText(fmtDate(a.date))).toBeInTheDocument();
            expect(w.getByText(fmtNum(a.quantity))).toBeInTheDocument();
            expect(w.getByText(fmtNum(a.cif_fc))).toBeInTheDocument();
            expect(w.getByText(fmtNum(a.cif_fc / a.quantity))).toBeInTheDocument();
            expect(w.getByText(a.status)).toBeInTheDocument();
            expect(w.getByRole("button", { name: "Copy allotment number" })).toBeInTheDocument();
        }
    });

    it("shows a dash rate for zero quantity and has no links", () => {
        hook.data = [{ ...make(1)[0], quantity: 0 }];
        render(<AllotmentsTab licenseId={1} isActive />);
        const row = screen.getAllByRole("row")[1];
        expect(within(row).getAllByText("—").length).toBeGreaterThan(0);
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
    });

    it("footer shows outstanding allotted (excludes BOE-linked) and gross separately", () => {
        // rows: ALT-100 Linked to BOE 5000, ALT-101 Approved 5010, ALT-102 Allotted 5020
        hook.data = make(3);
        render(<AllotmentsTab licenseId={1} isActive />);
        expect(screen.getByText(/Outstanding Allotted/)).toBeInTheDocument();
        expect(screen.queryByText(/Total Allotted/)).not.toBeInTheDocument();
        // gross (old, double-counting footer figure) kept as a labelled secondary value
        expect(screen.getByText(/Gross allotted/)).toHaveTextContent(fmtNum(15030));
        // headline = engine ALLOTMENT CIF component: 5010 + 5020
        expect(screen.getByText(/Outstanding CIF:/)).toHaveTextContent(fmtNum(10030));
    });
});
