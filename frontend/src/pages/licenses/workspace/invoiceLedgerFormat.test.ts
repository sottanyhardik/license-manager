import { describe, expect, it } from "vitest";
import {
  LEDGER_EMPTY,
  compareDecimal,
  formatCifAmount,
  formatExchangeRate,
  formatInrAmount,
  formatLedgerDate,
  uniqueCurrency,
} from "./invoiceLedgerFormat";
import { ledgerRow } from "./testData";

describe("ledger money formatting", () => {
  it("shows an en dash, never a zero, for null, undefined and blank amounts", () => {
    expect(formatCifAmount(null)).toBe(LEDGER_EMPTY);
    expect(formatCifAmount(undefined)).toBe(LEDGER_EMPTY);
    expect(formatCifAmount("  ")).toBe(LEDGER_EMPTY);
    expect(formatInrAmount(null)).toBe(LEDGER_EMPTY);
    expect(LEDGER_EMPTY).toBe("–");
  });

  it("groups INR with Indian grouping and two decimals", () => {
    expect(formatInrAmount("1702314.00")).toBe("17,02,314.00");
    expect(formatInrAmount("1238942")).toBe("12,38,942.00");
    // Beyond float precision, grouping is still exact because it works on the digits.
    expect(formatInrAmount("12345678901234567890.5")).toBe("1,23,45,67,89,01,23,45,67,890.50");
  });

  it("groups CIF with thousands separators and keeps the stored decimals", () => {
    expect(formatCifAmount("92128.06")).toBe("92,128.06");
    expect(formatCifAmount("5")).toBe("5.00");
    expect(formatCifAmount("1.005")).toBe("1.005");
    expect(formatCifAmount("1234567")).toBe("1,234,567.00");
  });

  it("keeps the minus sign on negative amounts", () => {
    expect(formatCifAmount("-1000.00")).toBe("-1,000.00");
    expect(formatInrAmount("-84000.00")).toBe("-84,000.00");
  });

  it("shows exchange rates exactly as stored", () => {
    expect(formatExchangeRate("83.5600")).toBe("83.5600");
    expect(formatExchangeRate(null)).toBe(LEDGER_EMPTY);
  });
});

describe("ledger dates", () => {
  it("shows ISO dates as DD-MM-YYYY and an empty date as an en dash", () => {
    expect(formatLedgerDate("2025-02-25")).toBe("25-02-2025");
    expect(formatLedgerDate(null)).toBe(LEDGER_EMPTY);
    expect(formatLedgerDate("not a date")).toBe("not a date");
  });
});

describe("exact decimal ordering", () => {
  it("treats equal values as equal regardless of trailing zeros or a negative zero", () => {
    expect(compareDecimal("100.5", "100.50")).toBe(0);
    expect(compareDecimal("-0.00", "0")).toBe(0);
  });

  it("orders negatives, fractions and integers without converting to floats", () => {
    expect(compareDecimal("-5", "2")).toBeLessThan(0);
    expect(compareDecimal("10", "9.99")).toBeGreaterThan(0);
    expect(compareDecimal("-10", "-9")).toBeLessThan(0);
    expect(compareDecimal("0.10", "0.9")).toBeLessThan(0);
  });

  it("sorts an empty value after every number", () => {
    expect(compareDecimal(null, "1")).toBeGreaterThan(0);
    expect(compareDecimal("-1", null)).toBeLessThan(0);
  });
});

describe("ledger currency", () => {
  it("names the one currency every row uses, or nothing when they differ", () => {
    expect(uniqueCurrency([ledgerRow({ line_id: 1, trade_id: 1, type: "SALE", invoice: "A" })])).toBe("USD");
    const mixed = [
      ledgerRow({ line_id: 1, trade_id: 1, type: "SALE", invoice: "A" }),
      ledgerRow({ line_id: 2, trade_id: 2, type: "SALE", invoice: "B", source: { type: "trade", id: 2, line_id: 2, currency: "EUR" } }),
    ];
    expect(uniqueCurrency(mixed)).toBeNull();
  });
});
