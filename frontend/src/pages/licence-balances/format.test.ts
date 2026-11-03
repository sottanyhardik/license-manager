import { describe, expect, it } from "vitest";
import {
  NOT_COMPUTED,
  formatCif,
  formatCount,
  formatDecimal,
  formatIsoDate,
  formatQty,
  isNegativeDecimal,
  isZeroDecimal,
  sameDecimal,
} from "./format";

describe("formatDecimal (strings in, strings out)", () => {
  it("groups integer digits with Indian grouping and pads the fraction", () => {
    expect(formatDecimal("1234567.5", 2)).toBe("12,34,567.50");
    expect(formatDecimal("1000", 2)).toBe("1,000.00");
    expect(formatDecimal("12", 2)).toBe("12.00");
  });

  it("preserves a negative sign from the string", () => {
    expect(formatDecimal("-40", 2)).toBe("-40.00");
    expect(formatDecimal("-1234.5", 2)).toBe("-1,234.50");
  });

  it("never rounds digits beyond the requested precision", () => {
    expect(formatDecimal("1.23456", 2)).toBe("1.23456");
  });

  it("shows the not-computed marker for null, undefined and blank", () => {
    expect(formatDecimal(null, 2)).toBe(NOT_COMPUTED);
    expect(formatDecimal(undefined, 3)).toBe(NOT_COMPUTED);
    expect(formatDecimal("  ", 2)).toBe(NOT_COMPUTED);
  });

  it("returns unrecognised input unchanged instead of guessing", () => {
    expect(formatDecimal("n/a", 2)).toBe("n/a");
  });

  it("formats CIF to 2 decimals and quantity to 3 decimals", () => {
    expect(formatCif("250")).toBe("250.00");
    expect(formatQty("12.5", "KGS")).toBe("12.500 KGS");
    expect(formatQty("12.5")).toBe("12.500");
  });

  it("does not attach a unit to a missing quantity", () => {
    expect(formatQty(null, "KGS")).toBe(NOT_COMPUTED);
  });
});

describe("sign and zero checks", () => {
  it("detects a strictly negative amount", () => {
    expect(isNegativeDecimal("-0.01")).toBe(true);
    expect(isNegativeDecimal("-0.00")).toBe(false);
    expect(isNegativeDecimal("0.00")).toBe(false);
    expect(isNegativeDecimal(null)).toBe(false);
  });

  it("treats every spelling of zero as zero, and empty text as not zero", () => {
    expect(isZeroDecimal("0")).toBe(true);
    expect(isZeroDecimal("-0.000")).toBe(true);
    expect(isZeroDecimal("1")).toBe(false);
    expect(isZeroDecimal("")).toBe(false);
    expect(isZeroDecimal(null)).toBe(false);
  });
});

describe("sameDecimal (string comparison, no float)", () => {
  it("matches equal values regardless of trailing zeros or negative zero", () => {
    expect(sameDecimal("100.5", "100.50")).toBe(true);
    expect(sameDecimal("-0.00", "0")).toBe(true);
    expect(sameDecimal("0010.000", "10")).toBe(true);
  });

  it("does not match different values or missing values", () => {
    expect(sameDecimal("100.50", "100.51")).toBe(false);
    expect(sameDecimal(null, "0")).toBe(false);
    expect(sameDecimal("abc", "abc")).toBe(false);
  });
});

describe("date and count formatting", () => {
  it("formats ISO dates without a timezone shift", () => {
    expect(formatIsoDate("2027-03-31")).toBe("31 Mar 2027");
    expect(formatIsoDate(null)).toBe(NOT_COMPUTED);
    expect(formatIsoDate("sometime")).toBe("sometime");
  });

  it("groups counts", () => {
    expect(formatCount(1234)).toBe("1,234");
  });
});
