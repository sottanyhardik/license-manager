import { describe, expect, it } from "vitest";

import {
    buildLicensePurchaseProfitReportPath,
    hasLicensePurchaseProfitReportParams,
    parseLicensePurchaseProfitReportParams,
} from "./buildLicensePurchaseProfitReportPath";

/** Pulls just the query string back out of a built path, as a
 * `URLSearchParams` — what the filters hook actually parses on mount. */
function queryParamsOf(path: string): URLSearchParams {
    return new URLSearchParams(path.split("?")[1] ?? "");
}

describe("buildLicensePurchaseProfitReportPath", () => {
    it("builds a full URL with every filter populated", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "excel",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "E126",
            licenseNumber: "  DFIA-1  ",
            excludeLicenseNumber: " DFIA-2, DFIA-3 ",
            exporter: { value: 42, label: "Acme Exports" },
        });

        expect(url).toBe(
            "reports/license-purchase-profit/?format=excel&from_date=2026-01-01&to_date=2026-01-31&norm=E126&license_number=DFIA-1&exclude_license_number=DFIA-2%2C+DFIA-3&exporter_id=42",
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

describe("parseLicensePurchaseProfitReportParams", () => {
    it("round-trips every filter: build a path, parse its query string, get the same values back", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "json",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "E126",
            licenseNumber: "DFIA-1",
            excludeLicenseNumber: ["DFIA-2", "DFIA-3"],
            exporter: 42,
        });

        const parsed = parseLicensePurchaseProfitReportParams(queryParamsOf(url));

        expect(parsed).toEqual({
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            norm: "E126",
            licenseNumber: "DFIA-1",
            excludeLicenseNumber: ["DFIA-2", "DFIA-3"],
            exporter: 42,
        });
    });

    it("round-trips an exporter option object the same as a raw id", () => {
        const url = buildLicensePurchaseProfitReportPath({
            format: "json",
            fromDate: "2026-01-01",
            toDate: "2026-01-31",
            exporter: { value: 7, label: "Acme Exports" },
        });

        const parsed = parseLicensePurchaseProfitReportParams(queryParamsOf(url));

        expect(parsed.exporter).toBe(7);
    });

    it("falls back to defaults for every filter omitted from the query string", () => {
        const parsed = parseLicensePurchaseProfitReportParams(new URLSearchParams());

        expect(parsed).toEqual({
            fromDate: "",
            toDate: "",
            norm: "All",
            licenseNumber: "",
            excludeLicenseNumber: [],
            exporter: null,
        });
    });

    it("parses a single exclude_license_number value (no comma) into a one-item array", () => {
        const parsed = parseLicensePurchaseProfitReportParams(new URLSearchParams("exclude_license_number=DFIA-9"));

        expect(parsed.excludeLicenseNumber).toEqual(["DFIA-9"]);
    });
});

describe("hasLicensePurchaseProfitReportParams", () => {
    it("is false for an empty query string", () => {
        expect(hasLicensePurchaseProfitReportParams(new URLSearchParams())).toBe(false);
    });

    it("is false when the query string carries only unrelated params", () => {
        expect(hasLicensePurchaseProfitReportParams(new URLSearchParams("tab=overview"))).toBe(false);
    });

    it("is true when at least one of this report's filter params is present", () => {
        expect(hasLicensePurchaseProfitReportParams(new URLSearchParams("from_date=2026-01-01"))).toBe(true);
        expect(hasLicensePurchaseProfitReportParams(new URLSearchParams("exporter_id=7"))).toBe(true);
    });
});
