import { describe, expect, it } from "vitest";

import {
    buildLicenseEndpoint,
    formatFiniteDecimal,
    normalizeItemOptions,
    normalizeLicenseBalanceData,
    normalizeUsageData,
    toSafeLicensePathSegment,
} from "./LicenseBalanceModal";

describe("LicenseBalanceModal helpers", () => {
    it("builds license API paths from safe path segments", () => {
        expect(toSafeLicensePathSegment(" 42 ")).toBe("42");
        expect(buildLicenseEndpoint(42)).toBe("licenses/42/");
        expect(buildLicenseEndpoint("LIC 1", "balance-excel/")).toBe("licenses/LIC%201/balance-excel/");
    });

    it("rejects blank and unsafe license path segments", () => {
        expect(() => toSafeLicensePathSegment("")).toThrow("valid license id");
        expect(() => toSafeLicensePathSegment("12/../balance-pdf")).toThrow("valid license id");
        expect(() => toSafeLicensePathSegment("12\\balance-pdf")).toThrow("valid license id");
        expect(() => toSafeLicensePathSegment("12?format=xlsx")).toThrow("valid license id");
    });

    it("formats malformed numeric balance values as zero", () => {
        expect(formatFiniteDecimal("123.456")).toBe("123.46");
        expect(formatFiniteDecimal(null)).toBe("0.00");
        expect(formatFiniteDecimal("not-a-number")).toBe("0.00");
        expect(formatFiniteDecimal(Number.POSITIVE_INFINITY)).toBe("0.00");
    });

    it("normalizes malformed usage collections", () => {
        expect(normalizeUsageData({ boes: [{ id: 1 }], allotments: "bad" })).toEqual({
            boes: [{ id: 1 }],
            allotments: [],
        });
        expect(normalizeUsageData(null)).toEqual({ boes: [], allotments: [] });
    });

    it("normalizes license item collections without dropping other fields", () => {
        expect(
            normalizeLicenseBalanceData({
                id: 1,
                license_number: "LIC-1",
                import_license: "bad",
                export_license: [{ id: 2 }],
            }),
        ).toEqual({
            id: 1,
            license_number: "LIC-1",
            import_license: [],
            export_license: [{ id: 2 }],
        });

        expect(normalizeLicenseBalanceData(null)).toBeNull();
    });

    it("normalizes async item-select options from paginated responses", () => {
        expect(
            normalizeItemOptions({
                results: [
                    { id: 1, name: "Alpha" },
                    { id: null, name: "Missing id" },
                    { id: 2, name: null },
                    { id: 3, name: 99 },
                ],
            }),
        ).toEqual([
            { value: 1, label: "Alpha" },
            { value: 3, label: "99" },
        ]);

        expect(normalizeItemOptions({ results: "bad" })).toEqual([]);
    });
});
