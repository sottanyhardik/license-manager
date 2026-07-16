import { describe, expect, it } from "vitest";

import { buildItemPivotReportPath, toFiniteNumber } from "./ItemPivotReport";

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
