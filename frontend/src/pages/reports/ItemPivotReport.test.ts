import { describe, expect, it } from "vitest";

import { buildItemPivotReportPath, itemSummaryName, itemSummaryRowsFromMatrix, itemSummarySubtotal, toFiniteNumber, visibleItemFields } from "./itemPivotReportUtils";

describe("ItemPivotReport helpers", () => {
    it("builds encoded item-pivot report URLs from active filters", () => {
        const url = buildItemPivotReportPath({
            format: "excel",
            normClass: "E 132",
            selectedCompanies: [12, " 34 "],
            excludeCompanies: ["56"],
            minBalance: "500",
            licenseStatus: "expiring_soon",
            expiryDateFrom: "2026-01-01",
            expiryDateTo: "2026-12-31",
            purchaseStatus: ["GE", "MI"],
        });

        expect(url).toBe(
            "reports/item-pivot/?format=excel&days=30&sion_norm=E+132&company_ids=12%2C34&exclude_company_ids=56&min_balance=500&license_status=expiring_soon&expiry_date_from=2026-01-01&expiry_date_to=2026-12-31&purchase_status=GE%2CMI",
        );
    });

    it("omits blank optional filters and falls back for malformed numeric filters", () => {
        const url = buildItemPivotReportPath({
            format: "json",
            normClass: " ",
            selectedCompanies: [null, ""],
            excludeCompanies: [],
            minBalance: "bad",
            licenseStatus: "",
            expiryDateFrom: " ",
            expiryDateTo: null,
            purchaseStatus: ["", "GE"],
        });

        expect(url).toBe("reports/item-pivot/?format=json&days=30&min_balance=200&license_status=active&purchase_status=GE");
    });

    it("normalizes finite numeric values without propagating NaN", () => {
        expect(toFiniteNumber("10.5")).toBe(10.5);
        expect(toFiniteNumber(null, 7)).toBe(7);
        expect(toFiniteNumber("not-a-number", 3)).toBe(3);
        expect(toFiniteNumber(Number.POSITIVE_INFINITY, 2)).toBe(2);
    });
});

describe("ItemPivotReport empty field columns", () => {
    const groupWith = (licenseItems: any[], total: any) => ({
        totals: { items: { "FRUIT": total } },
        licenses: licenseItems.map((items) => ({ items: { FRUIT: items } })),
    });
    const item = { key: "FRUIT", product_category: "FRUIT" };
    const keysOf = (group: any) => visibleItemFields(item, group).map(({ key }) => key);

    it("keeps HSN CODE and DESCRIPTION even when they carry no value", () => {
        expect(keysOf(groupWith([{}], {}))).toEqual(["hsn_code", "description"]);
    });

    it("hides RESTRICTION % and RESTRICTION VAL when every licence cell and the total are null or 0", () => {
        const group = groupWith([{ restriction_percent: 0, restriction_value: null, total_qty: 5 }], { total_qty: 5 });

        expect(keysOf(group)).not.toContain("restriction_percent");
        expect(keysOf(group)).not.toContain("restriction_value");
        expect(keysOf(group)).toContain("total_qty");
    });

    it("hides BILLED QTY and BILLED CIF when they are 0 everywhere", () => {
        const group = groupWith([{ billed_qty: 0, billed_cif: 0, allotted_qty: 3 }], { billed_qty: 0, billed_cif: 0, allotted_qty: 3 });

        expect(keysOf(group)).not.toContain("billed_qty");
        expect(keysOf(group)).not.toContain("billed_cif");
        expect(keysOf(group)).toContain("allotted_qty");
    });

    it("keeps a column when only one licence or only the total carries a non-zero value", () => {
        const onlyInOneLicence = groupWith([{ billed_qty: 0 }, { billed_qty: 2 }], { billed_qty: 2 });
        const onlyInTotal = groupWith([{ billed_qty: 0 }], { billed_qty: 2 });

        expect(keysOf(onlyInOneLicence)).toContain("billed_qty");
        expect(keysOf(onlyInTotal)).toContain("billed_qty");
    });

    it("gives a RUTILE block its UNIT PRICE column only when it has a value", () => {
        const rutile = { key: "RUTILE", product_category: "RUTILE" };
        const withPrice = { licenses: [{ items: { RUTILE: { unit_price: 2.5 } } }], totals: { items: {} } };
        const withoutPrice = { licenses: [{ items: { RUTILE: { unit_price: null } } }], totals: { items: {} } };

        expect(visibleItemFields(rutile, withPrice).map(({ label }) => label)).toContain("UNIT PRICE");
        expect(visibleItemFields(rutile, withoutPrice).map(({ label }) => label)).not.toContain("UNIT PRICE");
    });
});

describe("Item Summary rows from the notification matrix", () => {
    const group = {
        item_groups: [{ key: "RUTILE:A3627", name: "RUTILE - A3627", sion: "A3627", product_category: "RUTILE" }],
        totals: { items: { "RUTILE:A3627": { total_qty: "1000.00", allotted_qty: "0.00", allotted_cif: "0.00", debited_qty: "200.00", boe_used_cif: "300.00", balance_qty: "800.00", unit_price: "2.61", plan_qty: "100.00", planned_cif: "261.00" } } },
        licenses: [
            { items: { "RUTILE:A3627": { hsn_code: "32061190" } } },
            { items: { "RUTILE:A3627": { hsn_code: "32061190" } } },
            { items: {} },
        ],
    };

    it("reads each row from the matrix totals and counts only licences holding the item", () => {
        const [row] = itemSummaryRowsFromMatrix(group);
        expect(row).toMatchObject({
            item_name: "RUTILE", sion: "A3627", hsn_codes: ["32061190"], license_count: 2,
            total_qty: "1000.00", boe_used_qty: "200.00", boe_used_cif: "300.00", balance_qty: "800.00",
            unit_price: "2.61", planned_qty: "100.00", planned_cif: "261.00",
        });
    });

    it("sums quantities for the SUBTOTAL and takes the unit price from the priced rows only", () => {
        const [rutile] = itemSummaryRowsFromMatrix(group);
        const unpriced = { unit_price: null, balance_qty: "50.00", total_qty: "5.00" };
        const subtotal = itemSummarySubtotal([rutile, unpriced]);
        expect(subtotal.total_qty).toBe(1005);
        expect(subtotal.balance_qty).toBe(850);
        expect(subtotal.unit_price).toBeCloseTo(2.61);
    });
});

describe("Item Summary names", () => {
    it("names a row by its product category instead of a raw import description", () => {
        const group = {
            item_groups: [{ key: "ALUMINIUM OXIDE:A3627", name: "(a) Aluminium Oxide 28182000 (b) Zinc Oxide 28170010", sion: "A3627", product_category: "ALUMINIUM OXIDE" }],
            totals: { items: {} },
            licenses: [],
        };
        expect(itemSummaryRowsFromMatrix(group)[0].item_name).toBe("ALUMINIUM OXIDE");
    });

    it("falls back to the item name when there is no product category", () => {
        expect(itemSummaryName({ product_category: "UNCLASSIFIED", item_name: "SOME ITEM" })).toBe("SOME ITEM");
        expect(itemSummaryName({ product_category: null, item_name: "SOME ITEM" })).toBe("SOME ITEM");
    });
});
