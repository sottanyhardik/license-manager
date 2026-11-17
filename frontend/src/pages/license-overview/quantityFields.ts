/**
 * Server-authoritative per-import-item quantity fields (approved A-1).
 * The browser never computes available quantity; it renders what the API sends.
 */
export interface CanonicalQuantityFields {
    /** String Decimal (3dp), engine value floored at 0. */
    available_quantity_canonical?: string | null;
    /** String Decimal (3dp); shortfall when the item is over-utilised. */
    over_utilised_quantity?: string | null;
    is_quantity_over_utilised?: boolean | null;
}

type WithFallback = CanonicalQuantityFields & { available_quantity?: number | string | null };

/** Canonical value if present, else the existing server value (older API). Never computed. */
export function serverAvailableQuantity(item: WithFallback): number | string | null {
    return item.available_quantity_canonical ?? item.available_quantity ?? null;
}

export const isQuantityOverUtilised = (item: CanonicalQuantityFields): boolean => item.is_quantity_over_utilised === true;

export function overUsedLabel(item: CanonicalQuantityFields): string {
    return `Over-used by ${item.over_utilised_quantity ?? "—"}`;
}

/** Exhausted = server value is 0 and the item is not flagged over-utilised. */
export function isQuantityExhausted(item: WithFallback): boolean {
    const value = serverAvailableQuantity(item);
    return value != null && Number(value) === 0 && !isQuantityOverUtilised(item);
}
