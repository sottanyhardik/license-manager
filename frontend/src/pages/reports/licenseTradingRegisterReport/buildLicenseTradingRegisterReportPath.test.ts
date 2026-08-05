import { describe, expect, it } from "vitest";

import { buildLicenseTradingRegisterReportPath } from "./buildLicenseTradingRegisterReportPath";

describe("buildLicenseTradingRegisterReportPath", () => {
    it("builds a full URL with every filter populated", () => {
        const url = buildLicenseTradingRegisterReportPath({
            format: "excel",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "E126",
            licenseType: "DFIA",
            licenseNumber: "  DFIA-1  ",
            exporter: { value: 42, label: "Acme Exports" },
            item: { value: 7, label: "Vegetable Oil" },
            customer: { value: 11, label: "Acme Buyer" },
            supplier: { value: 12, label: "Acme Supplier" },
        });

        expect(url).toBe(
            "reports/license-trading-register-profit/?format=excel&from_date=2026-01-01&to_date=2026-01-31&norm=E126&license_type=DFIA&license_number=DFIA-1&exporter_id=42&item_id=7&customer_id=11&supplier_id=12",
        );
    });

    it("accepts raw ids (not wrapped in an option object)", () => {
        const url = buildLicenseTradingRegisterReportPath({
            format: "pdf",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            exporter: 7,
            item: 8,
            customer: 9,
            supplier: 10,
        });

        expect(url).toBe(
            "reports/license-trading-register-profit/?format=pdf&from_date=2026-01-01&to_date=2026-01-31&exporter_id=7&item_id=8&customer_id=9&supplier_id=10",
        );
    });

    it("omits blank optional filters and default 'All' norm/license type", () => {
        const url = buildLicenseTradingRegisterReportPath({
            format: "json",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "All",
            licenseType: "All",
            licenseNumber: "   ",
            exporter: null,
            item: null,
            customer: null,
            supplier: null,
        });

        expect(url).toBe("reports/license-trading-register-profit/?format=json&from_date=2026-01-01&to_date=2026-01-31");
    });

    it("omits from_date/to_date entirely when not yet selected", () => {
        const url = buildLicenseTradingRegisterReportPath({ format: "json" });

        expect(url).toBe("reports/license-trading-register-profit/?format=json");
    });
});
