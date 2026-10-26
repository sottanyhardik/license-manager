import { describe, expect, it } from "vitest";

import { buildItemPivotReportPath, toFiniteNumber, visibleItemFields } from "./itemPivotReportUtils";

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
