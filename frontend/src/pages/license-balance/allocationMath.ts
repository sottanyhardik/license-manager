/**
 * Pure allocation math for the Licence Balance Workspace's BOE allocation
 * drawer — deliberately framework-free so it's unit-testable without
 * rendering the drawer component.
 *
 * Core rule (fixes a reported bug): SELECTING a BOE/allotment as a
 * candidate is NOT the same as allocating its full remaining capacity to
 * it. The validation this module implements compares
 *   SUM(allocated CIF/Qty across selected rows) <= invoice's remaining CIF/Qty
 * never
 *   SUM(selected rows' OWN capacity) <= invoice's remaining CIF/Qty
 * — those are only the same number when every selected row happens to get
 * fully allocated, which auto-distribute (below) does NOT assume.
 */

export const ALLOCATION_EPS = 0.005;

export function round2(n: number): number {
    return Math.round(n * 100) / 100;
}

export interface AllocationCandidateCapacity {
    id: number | string;
    remainingQty: number;
    remainingCif: number;
}

export interface DistributedAllocation {
    id: number | string;
    qty: number;
    cif: number;
}

/**
 * Distributes `invoiceRemainingQty`/`invoiceRemainingCif` across
 * `candidates`, IN THE ORDER GIVEN (selection order — the caller is
 * responsible for ordering by when each candidate was checked), filling
 * each candidate up to its own remaining capacity before moving to the
 * next, and never exceeding either overall budget.
 *
 * Qty and CIF are distributed as two INDEPENDENT budgets (matching this
 * system's own data model, where a BOE/allotment row's qty and cif_fc are
 * independent decimal fields, not a strictly-derived rate) — a candidate
 * can be qty-capped while still having CIF budget left, or vice versa.
 *
 * Verified against the product spec's worked examples:
 *   174,240 remaining / two BOEs @ 87,120 each -> [87120, 87120] (exact fill)
 *   160,380 remaining / two BOEs @ 87,120 each -> [87120, 73260] (first BOE
 *     filled completely, second gets the remainder, 13,860 left on it)
 */
export function distributeAllocation(
    candidates: AllocationCandidateCapacity[],
    invoiceRemainingQty: number,
    invoiceRemainingCif: number,
): DistributedAllocation[] {
    let qtyBudget = Math.max(0, invoiceRemainingQty);
    let cifBudget = Math.max(0, invoiceRemainingCif);

    return candidates.map((candidate) => {
        if (qtyBudget <= ALLOCATION_EPS && cifBudget <= ALLOCATION_EPS) {
            return { id: candidate.id, qty: 0, cif: 0 };
        }
        const qty = round2(Math.max(0, Math.min(candidate.remainingQty, qtyBudget)));
        const cif = round2(Math.max(0, Math.min(candidate.remainingCif, cifBudget)));
        qtyBudget = Math.max(0, qtyBudget - qty);
        cifBudget = Math.max(0, cifBudget - cif);
        return { id: candidate.id, qty, cif };
    });
}

export interface AllocationTotals {
    invoiceRemainingQty: number;
    invoiceRemainingCif: number;
    allocatedQty: number;
    allocatedCif: number;
}

export interface AllocationValidation {
    overQty: boolean;
    overCif: boolean;
    valid: boolean;
    remainingQtyAfter: number;
    remainingCifAfter: number;
}

/**
 * The ONLY validation rule for the aggregate: SUM(allocated) vs. the
 * invoice's (or BOE's, when allocating allotments) own remaining capacity.
 * Never compares against candidates' combined capacity.
 */
export function validateAllocationTotals(totals: AllocationTotals): AllocationValidation {
    const overQty = totals.allocatedQty > totals.invoiceRemainingQty + ALLOCATION_EPS;
    const overCif = totals.allocatedCif > totals.invoiceRemainingCif + ALLOCATION_EPS;
    return {
        overQty,
        overCif,
        valid: !overQty && !overCif,
        remainingQtyAfter: round2(totals.invoiceRemainingQty - totals.allocatedQty),
        remainingCifAfter: round2(totals.invoiceRemainingCif - totals.allocatedCif),
    };
}

/**
 * Secondary, per-row guard: a single row's own allocated amount must not
 * exceed THAT row's own remaining capacity (independent of the aggregate
 * check above — the backend enforces this too via
 * `remaining_for_row_details_invoice_side`/`remaining_for_allotment_item`,
 * so this is a live pre-check, not the authoritative one).
 */
export function validateRowWithinCapacity(
    row: { qty: number; cif: number },
    candidate: AllocationCandidateCapacity,
): { overQty: boolean; overCif: boolean } {
    return {
        overQty: row.qty > candidate.remainingQty + ALLOCATION_EPS,
        overCif: row.cif > candidate.remainingCif + ALLOCATION_EPS,
    };
}
