import { describe, expect, it } from "vitest";

import {
    distributeAllocation,
    validateAllocationTotals,
    validateRowWithinCapacity,
} from "./allocationMath";

describe("distributeAllocation", () => {
    it("single BOE allocation — full invoice remaining fits within one BOE's capacity", () => {
        const result = distributeAllocation(
            [{ id: 1, remainingQty: 46493, remainingCif: 174240 }],
            46493,
            56020.35,
        );
        expect(result).toEqual([{ id: 1, qty: 46493, cif: 56020.35 }]);
    });

    it("multiple BOE allocation — exact combined fit (174,240 across two BOEs of 87,120 each)", () => {
        const result = distributeAllocation(
            [
                { id: 1, remainingQty: 1000, remainingCif: 87120 },
                { id: 2, remainingQty: 1000, remainingCif: 87120 },
            ],
            2000,
            174240,
        );
        expect(result).toEqual([
            { id: 1, qty: 1000, cif: 87120 },
            { id: 2, qty: 1000, cif: 87120 },
        ]);
        const sum = result.reduce((s, r) => s + r.cif, 0);
        expect(sum).toBe(174240);
    });

    it("partial allocation — invoice remaining (160,380) less than combined BOE capacity (174,240)", () => {
        // Qty capacities scaled consistently with CIF (871.2 units @ $100/unit
        // per BOE) so both budgets run out at the same candidate, matching a
        // realistic same-rate scenario.
        const result = distributeAllocation(
            [
                { id: 1, remainingQty: 871.2, remainingCif: 87120 },
                { id: 2, remainingQty: 871.2, remainingCif: 87120 },
            ],
            1603.8,
            160380,
        );
        // First BOE filled completely, second gets the remainder.
        expect(result).toEqual([
            { id: 1, qty: 871.2, cif: 87120 },
            { id: 2, qty: 732.6, cif: 73260 },
        ]);
        const remainingOnSecondBoe = 87120 - result[1].cif;
        expect(remainingOnSecondBoe).toBeCloseTo(13860, 2);
    });

    it("full allocation — selecting one BOE does not force its full capacity, distribution decides the amount", () => {
        // Invoice only needs a fraction of this BOE's capacity.
        const result = distributeAllocation(
            [{ id: 1, remainingQty: 1000, remainingCif: 87120 }],
            250,
            20000,
        );
        expect(result).toEqual([{ id: 1, qty: 250, cif: 20000 }]);
        // Selecting the BOE must NOT auto-fill its own full remaining (87,120).
        expect(result[0].cif).not.toBe(87120);
    });

    it("existing allocation interaction — invoice remaining already reduced by a prior allocation caps distribution", () => {
        // Invoice originally 174,240; 100,000 already allocated elsewhere ->
        // remaining passed in is only 74,240. Distribution must respect that,
        // not the invoice's original total.
        const invoiceRemainingAfterExisting = 174240 - 100000;
        const result = distributeAllocation(
            [
                { id: 1, remainingQty: 1000, remainingCif: 87120 },
                { id: 2, remainingQty: 1000, remainingCif: 87120 },
            ],
            2000,
            invoiceRemainingAfterExisting,
        );
        const sum = result.reduce((s, r) => s + r.cif, 0);
        expect(sum).toBeCloseTo(invoiceRemainingAfterExisting, 2);
        expect(result[0].cif).toBe(74240);
        expect(result[1].cif).toBe(0);
    });

    it("stops distributing once the budget is exhausted, leaving later candidates at zero", () => {
        const result = distributeAllocation(
            [
                { id: 1, remainingQty: 500, remainingCif: 50000 },
                { id: 2, remainingQty: 500, remainingCif: 50000 },
                { id: 3, remainingQty: 500, remainingCif: 50000 },
            ],
            500,
            50000,
        );
        expect(result[0]).toEqual({ id: 1, qty: 500, cif: 50000 });
        expect(result[1]).toEqual({ id: 2, qty: 0, cif: 0 });
        expect(result[2]).toEqual({ id: 3, qty: 0, cif: 0 });
    });
});

describe("validateAllocationTotals", () => {
    it("quantity validation — flags over-allocation on Qty even when CIF is within bounds", () => {
        const result = validateAllocationTotals({
            invoiceRemainingQty: 1000,
            invoiceRemainingCif: 100000,
            allocatedQty: 1200,
            allocatedCif: 90000,
        });
        expect(result.overQty).toBe(true);
        expect(result.overCif).toBe(false);
        expect(result.valid).toBe(false);
    });

    it("CIF validation — flags over-allocation on CIF even when Qty is within bounds", () => {
        const result = validateAllocationTotals({
            invoiceRemainingQty: 1000,
            invoiceRemainingCif: 100000,
            allocatedQty: 900,
            allocatedCif: 120000,
        });
        expect(result.overQty).toBe(false);
        expect(result.overCif).toBe(true);
        expect(result.valid).toBe(false);
    });

    it("is valid (green) when allocated exactly equals remaining — the reported false-positive case", () => {
        const result = validateAllocationTotals({
            invoiceRemainingQty: 2000,
            invoiceRemainingCif: 174240,
            allocatedQty: 2000,
            allocatedCif: 174240,
        });
        expect(result.valid).toBe(true);
        expect(result.overCif).toBe(false);
        expect(result.overQty).toBe(false);
        expect(result.remainingCifAfter).toBe(0);
    });

    it("is invalid when SUM(allocated) exceeds remaining, regardless of candidates' combined capacity", () => {
        // Combined candidate capacity is irrelevant to this check — only
        // what's actually been allocated matters.
        const result = validateAllocationTotals({
            invoiceRemainingQty: 100,
            invoiceRemainingCif: 56020.35,
            allocatedQty: 100,
            allocatedCif: 60000,
        });
        expect(result.overCif).toBe(true);
        expect(result.valid).toBe(false);
    });

    it("tolerates floating point noise within epsilon", () => {
        const result = validateAllocationTotals({
            invoiceRemainingQty: 2000,
            invoiceRemainingCif: 174240,
            allocatedQty: 2000,
            allocatedCif: 174240.001,
        });
        expect(result.valid).toBe(true);
    });
});

describe("validateRowWithinCapacity", () => {
    it("flags a manually-entered amount that exceeds a single row's own remaining capacity", () => {
        const result = validateRowWithinCapacity(
            { qty: 100, cif: 90000 },
            { id: 1, remainingQty: 200, remainingCif: 87120 },
        );
        expect(result.overCif).toBe(true);
        expect(result.overQty).toBe(false);
    });

    it("passes when the row's amount is within its own capacity", () => {
        const result = validateRowWithinCapacity(
            { qty: 100, cif: 50000 },
            { id: 1, remainingQty: 200, remainingCif: 87120 },
        );
        expect(result.overCif).toBe(false);
        expect(result.overQty).toBe(false);
    });
});
