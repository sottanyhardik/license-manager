import type { ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildItemReportPath, buildPlannedReportPath } from "./reportPaths";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...args: unknown[]) => get(...args), patch: vi.fn() } }));
vi.mock("../../api/axios", () => ({ default: { get: (...args: unknown[]) => get(...args), patch: vi.fn() } }));
vi.mock("@/components/ui/select", () => ({
    Select: ({ value, onValueChange, children }: { value: string; onValueChange: (v: string) => void; children: ReactNode }) => (
        <select aria-label="Planning Status" value={value} onChange={(e) => onValueChange(e.target.value)}>{children}</select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children: ReactNode }) => <option value={value}>{children}</option>,
}));

import ItemReport from "./ItemReport";
import { PRODUCTS_RECONCILED } from "./itemReport/__fixtures__/products";

const row = (id: number, licence: number, planned: boolean) => ({
    id, license_id: licence, license_number: `LIC-${licence}`, serial_number: id, product_description: `Item ${id}`, hs_code: "1905",
    item_names: [], quantity: 10, available_quantity: 5, available_balance: 500, unit_price: 1, balance_cif: 900, is_restricted: false,
    condition_type: "", notes: "", condition_sheet: "", unit: "kg", planned_quantity: planned ? 2 : 0, planned_cif: planned ? 4 : 0,
    plan_source: planned ? "manual" : "", planned_splits: [], is_planned: planned, license_date: null, license_expiry_date: null,
    ledger_date: null, exporter_name: "X", current_owner: null, latest_transfer: null,
});
const ALL = [row(1, 10, true), row(2, 10, false), row(3, 11, false)];
const COUNTS = { all: 3, planned: 1, unplanned: 2 };

function reportFor(url: string) {
    const status = new URLSearchParams(url.split("?")[1]).get("planning_status") ?? "all";
    const items = status === "planned" ? ALL.filter((r) => r.is_planned) : status === "unplanned" ? [] : ALL;
    return { report_date: "2026-11-20", total_items: items.length, planning_status: status, planning_counts: COUNTS, items };
}

const reportCalls = () => get.mock.calls.map(([u]) => String(u)).filter((u) => u.startsWith("reports/item-report/") && !u.includes("/products/"));
const lastCall = () => { const calls = reportCalls(); return calls[calls.length - 1] ?? ""; };

beforeEach(() => {
    get.mockReset();
    get.mockImplementation(async (url: string) => {
        if (String(url).startsWith("reports/item-report/products/")) return { data: PRODUCTS_RECONCILED };
        if (String(url).startsWith("reports/item-report/")) return { data: reportFor(String(url)) };
        return { data: [] }; // masters / options
    });
});

describe("Item Report — Planning Status", () => {
    it("loads ALL items by default without an item-name or search query, with backend counts", async () => {
        render(<MemoryRouter><ItemReport /></MemoryRouter>);
        await userEvent.click(screen.getByRole("button", { name: "By import item" })); // legacy view; product view is the default
        await waitFor(() => expect(reportCalls().length).toBeGreaterThan(0), { timeout: 3000 });
        expect(lastCall()).not.toContain("planning_status");
        expect(await screen.findByText("Item 1")).toBeInTheDocument();
        expect(screen.getByText("Item 2")).toBeInTheDocument();
        const select = screen.getByRole("combobox", { name: "Planning Status" });
        expect(within(select).getByRole("option", { name: "All Items (3)" })).toBeInTheDocument();
        expect(within(select).getByRole("option", { name: "Planned (1)" })).toBeInTheDocument();
        expect(within(select).getByRole("option", { name: "Unplanned (2)" })).toBeInTheDocument();
        expect(screen.queryByText("Select Filters to View Report")).not.toBeInTheDocument();
    });

    it("reloads server-side on change, keeps the selection, and shows a status-specific empty state", async () => {
        const user = userEvent.setup();
        render(<MemoryRouter><ItemReport /></MemoryRouter>);
        await userEvent.click(screen.getByRole("button", { name: "By import item" })); // legacy view; product view is the default
        await screen.findByText("Item 1");
        const select = screen.getByRole("combobox", { name: "Planning Status" });
        await user.selectOptions(select, "planned");
        await waitFor(() => expect(lastCall()).toContain("planning_status=planned"), { timeout: 3000 });
        await waitFor(() => expect(screen.queryByText("Item 2")).not.toBeInTheDocument());
        expect(screen.getByText("Item 1")).toBeInTheDocument();
        expect(select).toHaveValue("planned");
        await user.selectOptions(select, "unplanned");
        expect(await screen.findByText("No unplanned items match the current filters", {}, { timeout: 3000 })).toBeInTheDocument();
        expect(lastCall()).toContain("planning_status=unplanned");
    });
});

describe("planning_status query parameter", () => {
    it("is sent only for planned / unplanned and never by the Planned Report by default", () => {
        expect(buildItemReportPath({ format: "json", planningStatus: "planned" })).toContain("planning_status=planned");
        expect(buildItemReportPath({ format: "excel", planningStatus: "unplanned" })).toContain("planning_status=unplanned");
        expect(buildItemReportPath({ format: "json", planningStatus: "all" })).not.toContain("planning_status");
        expect(buildItemReportPath({ format: "json" })).not.toContain("planning_status");
        expect(buildPlannedReportPath({ format: "json", planningStatus: "all" })).not.toContain("planning_status");
    });
});
