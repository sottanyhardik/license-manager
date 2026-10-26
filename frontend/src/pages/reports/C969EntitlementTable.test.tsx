import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import C969EntitlementTable, { type C969Entitlement, type EntitlementRow } from "./C969EntitlementTable";

const data: C969Entitlement = {
    columns: [
        { key: "hsn_code", label: "HSN CODE" },
        { key: "description", label: "DESCRIPTION" },
        { key: "total_qty", label: "TOTAL QTY" },
        { key: "allotted_qty", label: "ALLOTTED QTY" },
        { key: "allotted_cif", label: "ALLOTTED CIF" },
        { key: "debited_qty", label: "DEBITED QTY" },
        { key: "debited_cif", label: "DEBITED CIF" },
        { key: "balance_qty", label: "BALANCE QTY" },
    ],
    rows: [
        {
            category: "AIR FILTER",
            hsn_code: "84213100",
            description: "AIR FILTER",
            total_qty: "77255.008",
            allotted_qty: "0.000",
            allotted_cif: "0.00",
            debited_qty: "3306.000",
            debited_cif: "1040164.930",
            balance_qty: "73949.008",
            line_count: 381,
            license_count: 202,
            source_descriptions: ["air filter"],
        },
        {
            category: "UNRECOGNISED (C969)",
            hsn_code: "",
            description: "UNRECOGNISED (C969)",
            total_qty: "259691.680",
            allotted_qty: "0.000",
            allotted_cif: "0.00",
            debited_qty: "38523.000",
            debited_cif: "242264.240",
            balance_qty: "221168.680",
            line_count: 2,
            license_count: 2,
            source_descriptions: [],
        },
    ],
};

describe("C969EntitlementTable", () => {
    it("shows exactly the eight standard columns in order, with no grouped header", () => {
        render(<C969EntitlementTable data={data} />);
        const headers = screen.getAllByRole("columnheader").map((th) => th.textContent);
        expect(headers).toEqual([
            "HSN CODE", "DESCRIPTION", "TOTAL QTY", "ALLOTTED QTY", "ALLOTTED CIF", "DEBITED QTY", "DEBITED CIF", "BALANCE QTY",
        ]);
        screen.getAllByRole("columnheader").forEach((th) => expect(th.getAttribute("colspan")).toBeNull());
    });

    it("renders one row per category with formatted quantities and CIF", () => {
        render(<C969EntitlementTable data={data} />);
        const bodyRows = screen.getAllByRole("row").slice(1);
        expect(bodyRows).toHaveLength(2);
        const air = within(bodyRows[0]).getAllByRole("cell").map((td) => td.textContent);
        expect(air).toEqual(["84213100", "AIR FILTER", "77,255.008", "0.000", "0.00", "3,306.000", "10,40,164.93", "73,949.008"]);
    });

    it("shows a dash for blank HSN codes instead of an empty cell", () => {
        render(<C969EntitlementTable data={data} />);
        const bodyRows = screen.getAllByRole("row").slice(1);
        const unrecognised = within(bodyRows[1]).getAllByRole("cell").map((td) => td.textContent);
        expect(unrecognised[0]).toBe("—");
        expect(unrecognised[1]).toBe("UNRECOGNISED (C969)");
    });
});

describe("C969 unclassified lines table", () => {
    it("lists each unclassified line with its licence, description and quantity", () => {
        const withItems: C969Entitlement = {
            ...data,
            unrecognised_items: [
                {
                    import_item_id: 10944,
                    serial_number: 13,
                    licence_number: "3011000939",
                    description: "CARBON CONTENTS LESS THAN 2 PERCENT HS CODE 72280000, 7229, 7214",
                    quantity: "259491.680",
                    unit: "nos",
                    current_classifiers: [],
                },
            ],
        };
        render(<C969EntitlementTable data={withItems} />);
        expect(screen.getByText("Unclassified C969 Lines — to classify")).toBeTruthy();
        expect(screen.getByText("3011000939")).toBeTruthy();
        expect(screen.getByText("2,59,491.680")).toBeTruthy();
        expect(screen.getByText("SUGGESTED CLASSIFIER")).toBeTruthy();
    });

    it("says so when no lines are unclassified", () => {
        render(<C969EntitlementTable data={{ ...data, unrecognised_items: [] }} />);
        expect(screen.getByText("No unclassified lines. Every C969 line is named.")).toBeTruthy();
    });
});

import { C969GroupSummary } from "./C969EntitlementTable";

describe("C969 per-notification item summary", () => {
    it("shows the BEARING row with its entitlement values and the category as the item name", () => {
        const bearing: EntitlementRow = {
            category: "BEARING",
            hsn_code: "84821020",
            description: "BEARING",
            total_qty: "523148.003",
            allotted_qty: "17025.000",
            allotted_cif: "462000.00",
            debited_qty: "45797.000",
            debited_cif: "4656259.730",
            balance_qty: "461925.003",
            line_count: 87,
            license_count: 38,
            source_descriptions: [],
        };
        render(<C969GroupSummary group={{ c969_entitlement: { columns: data.columns, rows: [bearing] } }} />);
        const bodyRows = screen.getAllByRole("row").slice(1);
        const cells = within(bodyRows[0]).getAllByRole("cell").map((td) => td.textContent);
        expect(cells).toEqual([
            "BEARING", "84821020", "38", "5,23,148.003", "17,025.000", "4,62,000.00", "45,797.000", "46,56,259.73", "4,61,925.003",
        ]);
    });
});
