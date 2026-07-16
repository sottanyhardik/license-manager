import { describe, expect, it } from "vitest";

import {
  formatInr,
  formatTruthyIndianNumber,
  formatTruthyInr,
  parseMasterDisplayDate,
} from "./masterDisplayFormatters";

describe("master display formatters", () => {
  it("preserves existing empty display for falsey row values", () => {
    expect(formatTruthyInr(0)).toBe("—");
    expect(formatTruthyInr("")).toBe("—");
    expect(formatTruthyIndianNumber(0, { maximumFractionDigits: 3 })).toBe("—");
  });

  it("formats populated values using the Indian locale", () => {
    expect(formatTruthyInr(1234567.8)).toBe("₹12,34,568");
    expect(formatTruthyIndianNumber(1234.5678, { maximumFractionDigits: 3 })).toBe("1,234.568");
  });

  it("formats aggregate currency values with zero preserved", () => {
    expect(formatInr(0)).toBe("₹0.00");
    expect(formatInr(123456.7)).toBe("₹1,23,456.70");
  });

  it("parses display dates through the shared date formatter", () => {
    expect(parseMasterDisplayDate("16-07-2026")?.getFullYear()).toBe(2026);
    expect(parseMasterDisplayDate(null)).toBeNull();
  });
});
