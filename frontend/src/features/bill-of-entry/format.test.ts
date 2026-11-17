/**
 * Pins the BOE card formatters' output (expected values were taken from the
 * original inline toLocaleString implementations) so the move onto
 * masterDisplayFormatters stays byte-identical.
 */
import { describe, expect, it } from "vitest";

import { fmtFc2, fmtInr, fmtInrExact, fmtQty } from "./format";

describe("BOE record-detail formatters", () => {
    it.each([
        [0, "—"],
        [null, "—"],
        ["1234567.89", "₹12,34,567.89"],
        ["1234567", "₹12,34,567"],
    ])("fmtInrExact(%j) -> %j", (input, expected) => {
        expect(fmtInrExact(input)).toBe(expected);
    });

    it("unit price keeps the backend's 0.001 scale via fmtQty", () => {
        expect(fmtQty("12.345")).toBe("12.345");
    });
});

describe("BOE card formatters", () => {
    it.each([
        [0, "—"],
        [null, "—"],
        [undefined, "—"],
        ["", "—"],
        ["0", "₹0"],
        ["1234.5678", "₹1,235"],
        [1234567.4, "₹12,34,567"],
        [-1234.5678, "₹-1,235"],
    ])("fmtInr(%j) -> %j", (input, expected) => {
        expect(fmtInr(input)).toBe(expected);
    });

    it.each([
        [0, "—"],
        [null, "—"],
        [undefined, "—"],
        ["", "—"],
        ["1234.5678", "1,234.568"],
        [1234567.1, "12,34,567.1"],
        [-1234.5678, "-1,234.568"],
        ["12", "12"],
    ])("fmtQty(%j) -> %j", (input, expected) => {
        expect(fmtQty(input)).toBe(expected);
    });

    it.each([
        [0, "—"],
        [null, "—"],
        [undefined, "—"],
        ["", "—"],
        ["1234.5678", "1,234.57"],
        [1234567.1, "12,34,567.1"],
        [-1234.5678, "-1,234.57"],
        ["12", "12"],
    ])("fmtFc2(%j) -> %j", (input, expected) => {
        expect(fmtFc2(input)).toBe(expected);
    });
});
