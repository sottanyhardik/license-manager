import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ItemReportTable from "./ItemReportTable";

// Two items on the SAME license (grouped block) + one item on a different
// license, matching the shape apps/license/views/item_report.py's
// generate_report() actually returns.
const ITEMS = [
    {
        id: 1,
        license_id: 100,
        license_number: "LIC-0001",
        license_date: "2025-01-01",
        license_expiry_date: "2026-01-01",
        ledger_date: "2025-06-01",
        exporter_name: "Acme Exports",
        serial_number: 1,
        condition_type: "",
        hs_code: "39021000",
        product_description: "PP Granules",
        item_names: [{ id: 1, name: "PP GRANULES" }],
        available_quantity: 1000,
        unit_price: 1.5,
        available_balance: 5000,
        balance_cif: 5000,
        planned_quantity: 100,
        planned_cif: 150,
        planned_splits: [],
        is_restricted: false,
        notes: "Some note",
        condition_sheet: "",
        latest_transfer: "",
    },
    {
        id: 2,
        license_id: 100,
        license_number: "LIC-0001",
        license_date: "2025-01-01",
        license_expiry_date: "2026-01-01",
        ledger_date: "2025-06-01",
        exporter_name: "Acme Exports",
        serial_number: 2,
        condition_type: "",
        hs_code: "39021000",
        product_description: "PP Granules",
        item_names: [{ id: 1, name: "PP GRANULES" }],
        available_quantity: 2000,
        unit_price: 1.5,
        available_balance: 5000,
        balance_cif: 5000,
        planned_quantity: 0,
        planned_cif: 0,
        planned_splits: [],
        is_restricted: false,
        notes: "Some note",
        condition_sheet: "",
        latest_transfer: "",
    },
    {
        id: 3,
        license_id: 200,
        license_number: "LIC-0002",
        license_date: "2025-02-01",
        license_expiry_date: "2026-02-01",
        ledger_date: null,
        exporter_name: "Beta Traders",
        serial_number: 1,
        condition_type: "AU",
        hs_code: "20089991",
        product_description: "Fruit Juice",
        item_names: [{ id: 2, name: "FRUIT JUICE" }],
        available_quantity: 300,
        unit_price: 2.5,
        available_balance: 900,
        balance_cif: 900,
        planned_quantity: 50,
        planned_cif: 125,
        planned_splits: [],
        is_restricted: true,
        notes: "",
        condition_sheet: "AU condition text",
        latest_transfer: "",
    },
];

const noop = () => {};

function renderTable(overrides: Partial<React.ComponentProps<typeof ItemReportTable>> = {}) {
    return render(
        <ItemReportTable
            items={ITEMS}
            itemNameMode="editable"
            itemNameOptions={[]}
            onItemNamesChange={noop}
            editingCell={null}
            editValue=""
            onEditValueChange={noop}
            onStartEdit={noop}
            onCancelEdit={noop}
            onSaveEdit={noop}
            {...overrides}
        />
    );
}

describe("ItemReportTable", () => {
    it("renders all 21 columns in the exact spec order (required columns, then the kept extras)", () => {
        renderTable();
        const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
        expect(headers).toEqual([
            "Sr No", "License No", "License Date", "License Expiry Date", "Ledger Date", "Exporter Name",
            "Serial Number", "Condition", "HSN Code", "Product Description", "Item Name",
            "Available Quantity", "Unit Price", "Available Balance", "Plan Qty", "Plan CIF",
            "Balance CIF", "Is Restricted", "Notes", "Condition Sheet", "Transfer Status",
        ]);
    });

    it("groups by license: license-level fields shown once (rowSpan), per-item fields shown on every row", () => {
        renderTable();

        // License-level values appear exactly once for the 2-item LIC-0001 group.
        expect(screen.getAllByText("LIC-0001")).toHaveLength(1);
        expect(screen.getAllByText("Acme Exports")).toHaveLength(1);

        // Per-item values (HSN, description) repeat once per raw row even
        // though both LIC-0001 rows share the same values.
        expect(screen.getAllByText("PP Granules")).toHaveLength(2);

        // The two different-license groups both render their own exporter.
        expect(screen.getByText("Beta Traders")).toBeInTheDocument();
    });

    it("computes totals from `totalsItems` (the full filtered set) rather than `items` (the current page)", () => {
        // Simulates pagination: only LIC-0002's single item is "on this page",
        // but totals must still reflect the full 3-item filtered set.
        renderTable({ items: [ITEMS[2]], totalsItems: ITEMS });

        const totalRow = screen.getByText("Total:").closest("tr") as HTMLElement;
        // Available Quantity: 1000 + 2000 + 300 = 3300.000
        expect(within(totalRow).getByText("3,300.000")).toBeInTheDocument();
        // Available Balance: unique per license — 5000 (LIC-0001) + 900 (LIC-0002) = 5900.00
        expect(within(totalRow).getByText("5,900.00")).toBeInTheDocument();
        // Plan Qty: 100 + 0 + 50 = 150.000
        expect(within(totalRow).getByText("150.000")).toBeInTheDocument();
        // Plan CIF: 150 + 0 + 125 = 275.00
        expect(within(totalRow).getByText("275.00")).toBeInTheDocument();
    });

    it("continues Sr No numbering from `startSrNo` across pages instead of restarting at 1", () => {
        renderTable({ items: [ITEMS[2]], totalsItems: ITEMS, startSrNo: 2 });
        const row = screen.getByText("LIC-0002").closest("tr") as HTMLElement;
        expect(within(row).getByText("3")).toBeInTheDocument();
    });
});
