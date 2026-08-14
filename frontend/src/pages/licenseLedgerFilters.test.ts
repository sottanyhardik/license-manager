import { describe, expect, it } from "vitest";

import { buildLicenseLedgerParams, defaultLicenseLedgerFilters } from "./licenseLedgerFilters";

describe("new License Ledger filter contract", () => {
    it("uses the canonical aggregate token for All Incentive", () => {
        const filters = defaultLicenseLedgerFilters(new Date(2026, 7, 14));
        filters.licenseType = "ALL_INCENTIVE";

        expect(buildLicenseLedgerParams(filters).get("license_type")).toBe("ALL_INCENTIVE");
    });

    it("serializes every supported filter without presentation data", () => {
        const filters = {
            ...defaultLicenseLedgerFilters(new Date(2026, 7, 14)),
            company: { value: 12, label: "Company A" }, licenseType: "MEIS", minBalance: " 100.50 ",
            search: " exporter ", ordering: "balance_value", activeOnly: true,
            norm: { value: "E1", label: "E1" }, purchaseStatus: { value: "GE", label: "Global Exim" },
            purchaseBill: "NO_PURCHASE_BILL", purchaseDateFrom: "2025-12-01", purchaseDateTo: "2025-12-31",
        };
        expect(Object.fromEntries(buildLicenseLedgerParams(filters))).toEqual({
            license_type: "MEIS", ordering: "balance_value", active_only: "true", buying_company_id: "12",
            min_balance: "100.50", search: "exporter", norm: "E1", purchase_status: "GE",
            purchase_bill: "NO_PURCHASE_BILL", purchase_date_from: "2025-12-01", purchase_date_to: "2025-12-31",
        });
    });

    it("uses the Indian Apr-Mar financial year defaults", () => {
        const filters = defaultLicenseLedgerFilters(new Date(2026, 0, 10));
        expect([filters.purchaseDateFrom, filters.purchaseDateTo]).toEqual(["2025-04-01", "2026-03-31"]);
    });

    it("uses the primitive ID returned by AsyncSelectField and never emits undefined", () => {
        const selected = { ...defaultLicenseLedgerFilters(), company: 766 };
        expect(buildLicenseLedgerParams(selected).get("buying_company_id")).toBe("766");

        const malformed = {
            ...defaultLicenseLedgerFilters(),
            company: { value: undefined } as unknown as typeof selected.company,
        };
        const params = buildLicenseLedgerParams(malformed);
        expect(params.has("buying_company_id")).toBe(false);
        expect(params.toString()).not.toContain("undefined");
    });
});
