import { describe, expect, it } from "vitest";

import { formatDashboardDate } from "./dashboardDate";

describe("formatDashboardDate", () => {
    it("formats UTC ISO instants without leaking timestamp fragments", () => {
        expect(formatDashboardDate("2026-08-22T10:32:51.272787Z")).toBe("22-08-2026");
        expect(formatDashboardDate("2026-08-22T10:32:51.272787Z", { includeTime: true })).toBe("22-08-2026 10:32");
    });

    it("preserves the instant in the supplied business timezone", () => {
        expect(formatDashboardDate("2026-08-22T23:45:00-04:00", { timeZone: "Asia/Kolkata" })).toBe("23-08-2026");
        expect(formatDashboardDate("2026-08-22T23:45:00-04:00", { timeZone: "Asia/Kolkata", includeTime: true })).toBe("23-08-2026 09:15");
    });

    it("handles UTC midnight boundaries, null, and invalid values safely", () => {
        expect(formatDashboardDate("2026-08-22T23:45:00Z", { timeZone: "Asia/Kolkata" })).toBe("23-08-2026");
        expect(formatDashboardDate(null)).toBe("—");
        expect(formatDashboardDate("not-a-date")).toBe("—");
    });
});
