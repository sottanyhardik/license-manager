import type { ReactNode } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DRILLDOWN_PKO, PRODUCTS_MISMATCH, PRODUCTS_RECONCILED, TOTALS } from "./itemReport/__fixtures__/products";
import { buildItemReportProductDrilldownPath, buildItemReportProductsPath } from "./reportPaths";
import { buildItemReportPath } from "./reportPaths";
import { reportQueryString } from "./itemReport/reportQueryString";
import type { ProductReport } from "./itemReport/productTypes";

const get = vi.fn();
const openAuthedFile = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...args: unknown[]) => get(...args), patch: vi.fn() } }));
vi.mock("../../api/axios", () => ({ default: { get: (...args: unknown[]) => get(...args), patch: vi.fn() } }));
vi.mock("@/utils/documentDownload", () => ({ openAuthedFile: (...args: unknown[]) => openAuthedFile(...args) }));
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

let productsResponse: ProductReport;
let drilldownImpl: () => Promise<{ data: unknown }>;

const calls = (needle: string) => get.mock.calls.map(([u]) => String(u)).filter((u) => u.includes(needle));
const productCalls = () => calls("/products/").filter((u) => !u.includes("/drilldown/"));
const lastProductCall = () => { const c = productCalls(); return c[c.length - 1] ?? ""; };

beforeEach(() => {
    get.mockReset();
    openAuthedFile.mockReset();
    productsResponse = PRODUCTS_RECONCILED;
    drilldownImpl = async () => ({ data: DRILLDOWN_PKO });
    get.mockImplementation(async (url: string) => {
        const u = String(url);
        if (u.startsWith("reports/item-report/products/drilldown/")) return drilldownImpl();
        if (u.startsWith("reports/item-report/products/")) return { data: productsResponse };
        if (u.startsWith("reports/item-report/?")) {
            return { data: { report_date: "2026-11-20", total_items: 0, planning_counts: { all: 0, planned: 0, unplanned: 0 }, items: [] } };
        }
        return { data: [] };
    });
});

const renderPage = () => render(<MemoryRouter><ItemReport /></MemoryRouter>);

describe("Item Report — product view", () => {
    it("loads products/ by default and shows PKO and PALM KERNEL OIL as separate rows", async () => {
        renderPage();
        expect(await screen.findByText("PKO")).toBeInTheDocument();
        expect(screen.getByText("PALM KERNEL OIL")).toBeInTheDocument();
        expect(productCalls().length).toBeGreaterThan(0);
        expect(calls("reports/item-report/?")).toHaveLength(0);
        expect(screen.getByText("Mixed units")).toBeInTheDocument();
        expect(screen.getByText("NOT ATTRIBUTED").closest("tr")).toHaveAttribute("data-not-attributed", "true");
    });

    it('shows "—" for a null balance_cif and "0.00" for a zero value', async () => {
        renderPage();
        const row = (await screen.findByText("PALM KERNEL OIL")).closest("tr")!;
        const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
        expect(cells).toContain("—"); // balance_cif null
        expect(cells).toContain("0.00"); // balance_qty "0.000", planned_qty "0.000"
        const pko = screen.getByText("PKO").closest("tr")!;
        expect(within(pko).queryAllByText("—").length).toBe(0);
    });

    it("renders totals from the backend, not summed client-side", async () => {
        renderPage();
        await screen.findByText("PKO");
        const footer = screen.getByTestId("product-totals");
        expect(within(footer).getByText("9,999.00")).toBeInTheDocument();
        expect(within(footer).getByText("88,888.00")).toBeInTheDocument();
        expect(within(footer).getByText("7,777.00")).toBeInTheDocument();
        expect(TOTALS.total_qty).toBe("9999.000");
    });

    it("shows the reconciled badge, and a warning listing differing metrics otherwise", async () => {
        const { unmount } = renderPage();
        expect(await screen.findByText("Reconciled with Item Pivot")).toBeInTheDocument();
        unmount();
        productsResponse = PRODUCTS_MISMATCH;
        renderPage();
        const badge = await screen.findByRole("alert");
        expect(badge).toHaveTextContent("balance_cif");
        expect(badge).toHaveTextContent("100.00");
        expect(badge).not.toHaveTextContent("total_qty"); // zero difference is not listed
        expect(screen.queryByText("Reconciled with Item Pivot")).not.toBeInTheDocument();
    });

    it("expands a row, fetches the drill-down with key + filters, and renders BOE / allotment / invoice refs", async () => {
        const user = userEvent.setup();
        renderPage();
        const toggle = await screen.findByRole("button", { name: /Expand PKO E126/ });
        expect(toggle).toHaveAttribute("aria-expanded", "false");
        await user.click(toggle);
        expect(await screen.findByText("BOE-7788 (2026-02-01) · Qty 120.00 · CIF 600.00 · Share 0.4")).toBeInTheDocument();
        expect(screen.getByText(/ALT-0042/)).toBeInTheDocument();
        expect(screen.getByText(/INV-2026-9/)).toBeInTheDocument();
        expect(screen.getByText(/PALM KERNEL OIL REFINED · HSN 15132110 · Norm E126/)).toBeInTheDocument();
        const expanded = screen.getByRole("button", { name: /Collapse PKO E126/ });
        expect(expanded).toHaveAttribute("aria-expanded", "true");
        expect(document.getElementById(expanded.getAttribute("aria-controls")!)).not.toBeNull();
        const url = new URL(calls("/drilldown/")[0], "http://x");
        expect(url.searchParams.get("key")).toBe("pko|E126");
        expect(url.searchParams.get("license_status")).toBe("active");
    });

    it("shows an error state when the drill-down fails", async () => {
        drilldownImpl = async () => { throw new Error("boom"); };
        const user = userEvent.setup();
        renderPage();
        await user.click(await screen.findByRole("button", { name: /Expand PKO E126/ }));
        expect(await screen.findByText(/Failed to load licence details/)).toBeInTheDocument();
    });

    it("sends license_numbers and planning_status, resets nothing else, and keeps filters across view switches", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("PKO");
        await user.type(screen.getByLabelText("Licence numbers"), "0311012345, 0311099999 0311012345");
        await user.selectOptions(screen.getByRole("combobox", { name: "Planning Status" }), "unplanned");
        await waitFor(() => expect(lastProductCall()).toContain("planning_status=unplanned"), { timeout: 3000 });
        const q = new URLSearchParams(lastProductCall().split("?")[1]);
        expect(q.get("license_numbers")).toBe("0311012345,0311099999");

        await user.click(screen.getByRole("button", { name: "By import item" }));
        await waitFor(() => expect(calls("reports/item-report/?").length).toBeGreaterThan(0));
        const importQ = new URLSearchParams(calls("reports/item-report/?").pop()!.split("?")[1]);
        expect(importQ.get("license_numbers")).toBe("0311012345,0311099999");
        expect(importQ.get("planning_status")).toBe("unplanned");
        expect(screen.getByLabelText("Licence numbers")).toHaveValue("0311012345, 0311099999 0311012345");
        expect(screen.getByRole("combobox", { name: "Planning Status" })).toHaveValue("unplanned");
    });

    it("exports Excel from products/ in product view and from the existing endpoint in import view", async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText("PKO");
        await user.click(screen.getByRole("button", { name: /Export/ }));
        await waitFor(() => expect(openAuthedFile).toHaveBeenCalledTimes(1));
        const first = String(openAuthedFile.mock.calls[0][0]);
        expect(first.startsWith("reports/item-report/products/?")).toBe(true);
        expect(first).toContain("_format=excel");

        await user.click(screen.getByRole("button", { name: "By import item" }));
        await user.click(screen.getByRole("button", { name: /Export/ }));
        await waitFor(() => expect(openAuthedFile).toHaveBeenCalledTimes(2));
        const second = String(openAuthedFile.mock.calls[1][0]);
        expect(second.startsWith("reports/item-report/?")).toBe(true);
        expect(second).toContain("_format=excel");
    });
});

describe("query builders", () => {
    it("omits license_numbers when empty (Planned Report query unchanged)", () => {
        expect(reportQueryString({ format: "json" })).not.toContain("license_numbers");
        expect(reportQueryString({ format: "json", licenseNumbers: "  " })).not.toContain("license_numbers");
        expect(buildItemReportPath({ format: "json", licenseNumbers: "A1 B2" })).toContain("license_numbers=A1%2CB2");
    });

    it("builds products and drilldown paths", () => {
        expect(buildItemReportProductsPath({ format: "excel" })).toMatch(/^reports\/item-report\/products\/\?_format=excel/);
        expect(buildItemReportProductDrilldownPath("a b|E1", { format: "json" })).toContain("drilldown/?key=a+b%7CE1&");
    });
});
