import { describe, expect, it } from "vitest";

import { buildItemReportPath, normalizeFilterValues, normalizeReportNumber } from "./ItemReport";

describe("ItemReport helpers", () => {
    it("builds encoded item report URLs from active filters", () => {
        const url = buildItemReportPath({
            format: "excel",
            selectedItemNames: [12, " 34 "],
            selectedCompanies: ["56"],
            excludeCompanies: [78],
            minBalance: "500",
            minAvailQty: "1000",
            licenseStatus: "expiring_soon",
            isRestricted: "true",
            purchaseStatus: ["GE", "MI"],
            productDescSearch: "foil & cap",
            hsnCodeSearch: "7607 20",
            selectedNorms: ["E1", "E132"],
            selectedNotifications: ["025/2023"],
            expiryDateFrom: "2026-01-01",
            expiryDateTo: "2026-12-31",
        });

        expect(url).toBe(
            "reports/item-report/?format=excel&item_names=12%2C34&company_ids=56&exclude_company_ids=78&min_balance=500&min_avail_qty=1000&license_status=expiring_soon&is_restricted=true&purchase_status=GE%2CMI&product_description=foil+%26+cap&hsn_code=7607+20&norms=E1%2CE132&notification_numbers=025%2F2023&expiry_date_from=2026-01-01&expiry_date_to=2026-12-31",
        );
    });

    it("omits blank optional filters and falls back for malformed numeric filters", () => {
        const url = buildItemReportPath({
            format: "json",
            selectedItemNames: ["", null, "  "],
            selectedCompanies: [],
            excludeCompanies: undefined,
            minBalance: "not-a-number",
            minAvailQty: Number.POSITIVE_INFINITY,
            licenseStatus: "",
            isRestricted: "all",
            purchaseStatus: ["", "SM"],
            productDescSearch: " ",
            hsnCodeSearch: null,
            selectedNorms: ["E5", ""],
            selectedNotifications: [],
            expiryDateFrom: "",
            expiryDateTo: " ",
        });

        expect(url).toBe(
            "reports/item-report/?format=json&min_balance=200&min_avail_qty=0&license_status=active&purchase_status=SM&norms=E5",
        );
    });

    it("normalizes filter values and finite report numbers", () => {
        expect(normalizeFilterValues([" A ", null, "", 7])).toEqual(["A", "7"]);
        expect(normalizeFilterValues(undefined)).toEqual([]);
        expect(normalizeReportNumber("10", 5)).toBe(10);
        expect(normalizeReportNumber("bad", 5)).toBe(5);
        expect(normalizeReportNumber(Number.NaN, 8)).toBe(8);
    });
});
