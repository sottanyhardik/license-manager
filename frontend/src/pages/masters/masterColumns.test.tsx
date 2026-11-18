import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";
import { masterEntities } from "../../routes/config";
import { defaultMasterColumns, MASTER_COLUMNS, resolveMasterColumns } from "./masterColumns";
import GenericMasterCards from "./tables/GenericMasterCards";

// The expanded row loads the full record (MasterRecordPanel) from the master API.
const { getSpy } = vi.hoisted(() => ({ getSpy: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy } }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy } }));

describe("master column configuration", () => {
    it("configures every registered master, and only registered masters", () => {
        const registered = masterEntities.map(m => m.entity).sort();
        expect(Object.keys(MASTER_COLUMNS).sort()).toEqual(registered);
    });

    it("leads Companies with the IEC, not the audit timestamp the API lists first", () => {
        const { columns, details } = resolveMasterColumns("companies", { list_display: ["modified_on", "iec", "name"] });
        expect(columns.map(c => c.field)).toEqual(["iec", "name", "pan", "gst_number"]);
        expect(columns[0].mono).toBe(true);
        expect(details).toContain("address_line_1");
    });

    it("never shows MDS sync internals as Unit Price columns", () => {
        const fields = resolveMasterColumns("unit-prices", {}).columns.map(c => c.field);
        expect(fields).toEqual(["name", "label", "unit_price"]);
    });

    it("default columns skip ids, sync internals, audit and status fields", () => {
        const { columns, details } = defaultMasterColumns({
            list_display: ["id", "master_uid", "sync_version", "created_on", "is_active", "code", "a", "b", "c", "d", "e"],
        });
        expect(columns.map(c => c.field)).toEqual(["code", "a", "b", "c", "d"]);
        expect(details).toEqual(["e"]);
    });
});

describe("GenericMasterCards rows (licence register anatomy)", () => {
    const company = {
        id: 7, iec: "0306084341", name: "ABHISHEK TRADE", pan: "AANPS1234Q", gst_number: "24AANPS1234Q1Z5",
        address_line_1: "12 Ring Road", address_line_2: "Surat", modified_on: "2026-11-01T10:00:00Z",
    };
    const records: Record<string, Record<string, unknown>> = {
        "masters/companies/7/": company,
        "masters/companies/8/": { ...company, id: 8, iec: "0306084342", address_line_1: "8 Canal Road" },
        "masters/companies/999/": { ...company, id: 999, iec: "0399999999", name: "FAR AWAY CO" },
        "masters/ports/3/": { id: 3, code: "INMAA1", name: "Chennai" },
    };
    const auth = { isSuperAdmin: () => true, hasRole: () => true, hasAnyRole: () => true } as unknown as React.ContextType<typeof AuthContext>;
    getSpy.mockImplementation((url: string) => {
        if (url in records) return Promise.resolve({ data: records[url] });
        if (url === "masters/companies/" || url === "masters/ports/") {
            return Promise.resolve({ data: { list_display: ["iec", "name"], form_fields: ["iec", "name"] } });
        }
        return Promise.reject({ response: { status: 404 } });
    });
    const renderRows = (data: Record<string, unknown>[], entityName = "companies", extra: Record<string, unknown> = {}) => render(
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <AuthContext.Provider value={auth}>
        <MemoryRouter>
            <GenericMasterCards
                loading={false}
                data={data}
                metadata={{ list_display: ["modified_on", "iec", "name", "pan", "gst_number"] }}
                entityName={entityName}
                entityTitle="Companies"
                filterParams={{}}
                currentPage={1}
                pageSize={25}
                navigate={vi.fn()}
                onDelete={vi.fn()}
                {...extra}
            />
        </MemoryRouter>
        </AuthContext.Provider>
        </QueryClientProvider>,
    );

    it("labels columns once in an aligned header and keeps one compact row per record", () => {
        renderRows([company, { ...company, id: 8, iec: "0306084342", name: "SECOND CO" }]);
        const header = screen.getByTestId("master-column-header");
        expect(Array.from(header.querySelectorAll("span.truncate")).map(s => s.textContent)).toEqual(["IEC", "Name", "PAN", "GSTIN"]);
        const rows = within(screen.getByRole("list", { name: "Companies" })).getAllByRole("listitem");
        expect(rows).toHaveLength(2);
        expect(within(rows[0]).getByRole("link", { name: "0306084341" })).toHaveAttribute("href", "/masters/companies/7");
        expect(within(rows[0]).getByText("ABHISHEK TRADE")).toBeInTheDocument();
        // Secondary details stay out of the collapsed row.
        expect(screen.queryByText("12 Ring Road")).not.toBeInTheDocument();
    });

    it("expands a row in place to the full record (inline panel), one row at a time", async () => {
        const user = userEvent.setup();
        sessionStorage.clear();
        renderRows([company, { ...company, id: 8, iec: "0306084342", address_line_1: "8 Canal Road" }]);
        await user.click(screen.getByRole("button", { name: "Expand 0306084341" }));
        const region = screen.getByRole("region", { name: "0306084341 details" });
        // The record is fetched and shown inline with its tabs; Details holds the secondary fields.
        await user.click(await within(region).findByRole("tab", { name: "Details" }));
        expect(within(region).getByText("12 Ring Road")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Collapse 0306084341" })).toHaveAttribute("aria-expanded", "true");

        // Clicking anywhere on another row's header (not a control) moves the expansion there.
        await user.click(within(screen.getAllByRole("listitem")[1]).getByText("ABHISHEK TRADE"));
        expect(screen.queryByRole("region", { name: "0306084341 details" })).not.toBeInTheDocument();
        const second = screen.getByRole("region", { name: "0306084342 details" });
        await user.click(await within(second).findByRole("tab", { name: "Details" }));
        expect(second).toHaveTextContent("8 Canal Road");

        // Collapsing returns to the compact list.
        await user.click(screen.getByRole("button", { name: "Collapse 0306084342" }));
        expect(screen.queryByRole("region", { name: /details$/ })).not.toBeInTheDocument();
    });

    it("opens the record inline from its identifier link (plain click), keeping the link for new tabs", async () => {
        const user = userEvent.setup();
        renderRows([{ id: 3, code: "INMAA1", name: "Chennai" }], "ports");
        const link = screen.getByRole("link", { name: "INMAA1" });
        expect(link).toHaveAttribute("href", "/masters/ports/3");
        await user.click(link);
        expect(screen.getByRole("region", { name: "INMAA1 details" })).toBeInTheDocument();
        expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
    });

    it("controlled by the URL owner: Open record and collapse report the lookup instead of navigating", async () => {
        const user = userEvent.setup();
        const onExpandedChange = vi.fn();
        renderRows([company, { ...company, id: 8, iec: "0306084342" }], "companies", { expandedLookup: "7", onExpandedChange });
        expect(screen.getByRole("region", { name: "0306084341 details" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Collapse 0306084341" }));
        expect(onExpandedChange).toHaveBeenLastCalledWith(null);
        await user.click(screen.getByRole("button", { name: "Actions for 0306084342" }));
        await user.click(screen.getByRole("menuitem", { name: "Open record" }));
        expect(onExpandedChange).toHaveBeenLastCalledWith("8");
    });

    it("shows a URL-opened record that is not on this page pinned above the list, with close", async () => {
        const user = userEvent.setup();
        const onExpandedChange = vi.fn();
        renderRows([company], "companies", { expandedLookup: "999", onExpandedChange });
        const pinned = screen.getByRole("article", { name: "Companies 999" });
        expect(within(pinned).getByText("Not on this page")).toBeInTheDocument();
        expect(await within(pinned).findByText("0399999999")).toBeInTheDocument();
        await user.click(within(pinned).getByRole("button", { name: "Close 999" }));
        expect(onExpandedChange).toHaveBeenLastCalledWith(null);
    });
});
