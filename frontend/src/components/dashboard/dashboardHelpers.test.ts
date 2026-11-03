import { describe, expect, it } from "vitest";

import { formatClockTime, formatCount, formatDaysToExpiry, formatMoney, formatPercent, formatQuantity, UNAVAILABLE } from "./formatters";
import { presetToDates, toIsoDate } from "./scope";
import { sortRows } from "./tableSort";

describe("formatters", () => {
    it("formats CIF as dollars and invoices as rupees with the right grouping", () => {
        expect(formatMoney("1234.5", "cif")).toBe("$1,234.50");
        expect(formatMoney("100000.00", "invoice")).toBe("₹1,00,000.00");
    });

    it("shows an unavailable marker for missing or invalid money, never zero", () => {
        expect(formatMoney(null)).toBe(UNAVAILABLE);
        expect(formatMoney(undefined)).toBe(UNAVAILABLE);
        expect(formatMoney("")).toBe(UNAVAILABLE);
        expect(formatMoney("not a number")).toBe(UNAVAILABLE);
    });

    it("keeps the sign on negative money", () => {
        expect(formatMoney("-5")).toBe("−$5.00");
    });

    it("formats percentages from the API value and marks a null base as unavailable", () => {
        expect(formatPercent(50)).toBe("50.00%");
        expect(formatPercent(null)).toBe(UNAVAILABLE);
    });

    it("formats counts and quantities without inventing zeros", () => {
        expect(formatCount(1234)).toBe("1,234");
        expect(formatCount(null)).toBe(UNAVAILABLE);
        expect(formatQuantity("20")).toBe("20.00");
    });

    it("describes days to expiry in words for the boundary cases", () => {
        expect(formatDaysToExpiry(-1)).toBe("Expired");
        expect(formatDaysToExpiry(0)).toBe("Today");
        expect(formatDaysToExpiry(3)).toBe("3 d");
        expect(formatDaysToExpiry(undefined)).toBe(UNAVAILABLE);
    });

    it("formats the local clock time for the refreshed stamp", () => {
        expect(formatClockTime(null)).toBe(UNAVAILABLE);
        expect(formatClockTime(new Date(2026, 10, 2, 9, 5))).toBe("09:05");
    });
});

describe("date presets", () => {
    const today = new Date(2026, 10, 2);

    it("uses the local calendar date", () => {
        expect(toIsoDate(today)).toBe("2026-11-02");
    });

    it("maps last 30 days to the 30 calendar days ending today, inclusive", () => {
        expect(presetToDates("last30", today)).toEqual({ date_from: "2026-10-04", date_to: "2026-11-02" });
    });

    it("maps last 90 days to 90 calendar days ending today, inclusive", () => {
        expect(presetToDates("last90", today)).toEqual({ date_from: "2026-08-05", date_to: "2026-11-02" });
    });

    it("maps year to date from the first of January", () => {
        expect(presetToDates("ytd", today)).toEqual({ date_from: "2026-01-01", date_to: "2026-11-02" });
    });

    it("sends no date parameters for all time", () => {
        expect(presetToDates("all", today)).toEqual({});
    });
});

describe("sortRows", () => {
    type Row = { name: string; value: number | null };
    const rows: Row[] = [
        { name: "b", value: 2 },
        { name: "a", value: null },
        { name: "c", value: 1 },
    ];
    const accessors = { name: (row: Row) => row.name, value: (row: Row) => row.value };

    it("returns the rows unchanged when no sort is set", () => {
        expect(sortRows(rows, null, accessors).map((row) => row.name)).toEqual(["b", "a", "c"]);
    });

    it("sorts numbers ascending and descending", () => {
        expect(sortRows(rows, { key: "value", direction: "ascending" }, accessors).map((row) => row.name)).toEqual(["c", "b", "a"]);
        expect(sortRows(rows, { key: "value", direction: "descending" }, accessors).map((row) => row.name)).toEqual(["b", "c", "a"]);
    });

    it("keeps missing values last in either direction", () => {
        const ascending = sortRows(rows, { key: "value", direction: "ascending" }, accessors);
        const descending = sortRows(rows, { key: "value", direction: "descending" }, accessors);
        expect(ascending[ascending.length - 1].name).toBe("a");
        expect(descending[descending.length - 1].name).toBe("a");
    });

    it("does not mutate the input", () => {
        const copy = [...rows];
        sortRows(rows, { key: "name", direction: "ascending" }, accessors);
        expect(rows).toEqual(copy);
    });
});
