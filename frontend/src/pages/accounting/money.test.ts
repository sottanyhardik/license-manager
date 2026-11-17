import { describe, expect, it } from "vitest";

import { drCr, formatMoney, isMoneyInput, sumMoney } from "./money";

describe("accounting money helpers", () => {
    it("formats Indian grouping without float", () => {
        expect(formatMoney("1160000.00")).toBe("11,60,000.00");
        expect(formatMoney("123456789012345678.91")).toBe("1,23,45,67,89,01,23,45,678.91");
        expect(formatMoney("-236")).toBe("-236.00");
        expect(formatMoney("0.5")).toBe("0.50");
        expect(formatMoney("-0.00")).toBe("0.00");
        expect(formatMoney(null)).toBe("—");
        expect(formatMoney("abc")).toBe("—");
        expect(formatMoney("0.00", { blankZero: true })).toBe("");
    });

    it("labels debit/credit balances", () => {
        expect(drCr("1000.00")).toBe("1,000.00 Dr");
        expect(drCr("-1160000.00")).toBe("11,60,000.00 Cr");
        expect(drCr("0")).toBe("0.00");
    });

    it("sums decimal strings exactly", () => {
        expect(sumMoney(["0.10", "0.20"])).toBe("0.30");
        expect(sumMoney(["1180000.00", "-20000.00"])).toBe("1160000.00");
        expect(sumMoney(["-5.05", "1.00"])).toBe("-4.05");
        expect(sumMoney([])).toBe("0.00");
    });

    it("validates money input", () => {
        expect(isMoneyInput("1000")).toBe(true);
        expect(isMoneyInput("1000.5")).toBe(true);
        expect(isMoneyInput("1,000")).toBe(false);
        expect(isMoneyInput("-1")).toBe(false);
    });
});
