import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { masterEntities } from "../../routes/config";
import { defaultMasterColumns, MASTER_COLUMNS, resolveMasterColumns } from "./masterColumns";
import GenericMasterCards from "./tables/GenericMasterCards";

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
    const renderRows = (data: Record<string, unknown>[], entityName = "companies", extra: Record<string, unknown> = {}) => render(
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
        </MemoryRouter>,
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

    it("expands a row in place to its secondary details, one row at a time", async () => {
        const user = userEvent.setup();
        renderRows([company, { ...company, id: 8, iec: "0306084342", address_line_1: "8 Canal Road" }]);
        await user.click(screen.getByRole("button", { name: "Expand 0306084341" }));
        const region = screen.getByRole("region", { name: "0306084341 details" });
        expect(within(region).getByText("12 Ring Road")).toBeInTheDocument();
        expect(within(region).getByRole("link", { name: "Open record" })).toHaveAttribute("href", "/masters/companies/7");
        expect(screen.getByRole("button", { name: "Collapse 0306084341" })).toHaveAttribute("aria-expanded", "true");

        // Clicking anywhere on another row's header (not a control) moves the expansion there.
        await user.click(within(screen.getAllByRole("listitem")[1]).getByText("ABHISHEK TRADE"));
        expect(screen.queryByRole("region", { name: "0306084341 details" })).not.toBeInTheDocument();
        expect(screen.getByRole("region", { name: "0306084342 details" })).toHaveTextContent("8 Canal Road");
    });

    it("shows no expand control when a master has nothing more to show", () => {
        renderRows([{ id: 3, code: "INMAA1", name: "Chennai" }], "ports");
        expect(screen.queryByRole("button", { name: /Expand/ })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "INMAA1" })).toBeInTheDocument();
    });
});
