import { describe, expect, it } from "vitest";
import { formatDate, formatDateForInput, formatDateTime, parseDate } from "./dateFormatter";

describe("dateFormatter", () => {
    it("handles leap day and year boundaries", () => {
        expect(formatDate("29-02-2024")).toBe("29-02-2024");
        expect(formatDate("2024-02-29")).toBe("29-02-2024");
        expect(formatDate("31-12-2025")).toBe("31-12-2025");
        expect(formatDate("2026-01-01")).toBe("01-01-2026");
        expect(formatDate(new Date(2025, 11, 31 + 1))).toBe("01-01-2026");
    });
    it("does not shift ISO date-only strings", () => {
        expect(formatDate("2025-03-01")).toBe("01-03-2025");
        expect(formatDateForInput("01-03-2025")).toBe("2025-03-01");
        expect(parseDate("2025-03-01")?.getDate()).toBe(1);
        expect(formatDateTime("2025-03-01")).toBe("01-03-2025 12:00");
    });
    it("formats DD-MM-YYYY datetimes, keeping midnight hours", () => {
        expect(formatDateTime("05-06-2025 00:30")).toBe("05-06-2025 00:30");
        expect(formatDateTime("05-06-2025 14:45")).toBe("05-06-2025 14:45");
    });
    it("renders ISO datetime with Z in local time", () => {
        const iso = "2025-06-05T10:15:00Z";
        const d = new Date(iso);
        const pad = (n: number) => String(n).padStart(2, "0");
        const expected = `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
        expect(formatDate(iso)).toBe(expected);
        expect(formatDateTime(iso)).toBe(`${expected} ${pad(d.getHours())}:${pad(d.getMinutes())}`);
    });
    it("returns empty for invalid or empty input", () => {
        expect(formatDate("")).toBe("");
        expect(formatDate(null)).toBe("");
        expect(formatDate("garbage")).toBe("");
        expect(formatDateTime(undefined)).toBe("");
        expect(formatDateTime("not a date")).toBe("");
        expect(formatDateForInput("")).toBe("");
    });
});
