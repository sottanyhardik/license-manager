import { describe, expect, it } from "vitest";

import { buildLicensePurchaseProfitReportPath } from "./buildLicensePurchaseProfitReportPath";

describe("buildLicensePurchaseProfitReportPath", () => {
    it("builds a full URL with every filter populated", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "excel",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "E126",
            licenseNumber: "  DFIA-1  ",
            exporter: { value: 42, label: "Acme Exports" },
        });

        expect(url).toBe(
            "reports/license-purchase-profit/?format=excel&from_date=2026-01-01&to_date=2026-01-31&norm=E126&license_number=DFIA-1&exporter_id=42",
        );
    });

    it("accepts a raw exporter id (not wrapped in an option object)", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "pdf",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            exporter: 7,
        });

        expect(url).toBe("reports/license-purchase-profit/?format=pdf&from_date=2026-01-01&to_date=2026-01-31&exporter_id=7");
    });

    it("omits blank optional filters and the default 'All' norm", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "json",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "All",
            licenseNumber: "   ",
            exporter: null,
        });

        expect(url).toBe("reports/license-purchase-profit/?format=json&from_date=2026-01-01&to_date=2026-01-31");
    });

    it("omits from_date/to_date entirely when not yet selected", () => {
        const url = buildLicensePurchaseProfitReportPath({ format: "json" });

        expect(url).toBe("reports/license-purchase-profit/?format=json");
    });
});
