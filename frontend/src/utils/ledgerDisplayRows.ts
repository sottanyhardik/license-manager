/**
 * LEDGER TRANSACTION DISPLAY RULE — the single frontend expression.
 *
 * Mirrors `backend/apps/license/domain/transaction_semantics.py`
 * (`select_display_rows`). The backend is the source of truth; this module
 * exists so screens, PDF and Excel all consume that rule from ONE place
 * instead of re-writing `if (type === 'PURCHASE')` in each component.
 *
 * The rule — presentation only:
 *   * Only PURCHASE and SALE are shown as ordinary transaction rows.
 *   * OPENING is shown ONLY when no PURCHASE exists, and then only as the
 *     starting-state row — never as an ordinary transaction, never inside a
 *     company group.
 *
 *   | PURCHASE | SALE | OPENING | displayed                |
 *   |----------|------|---------|--------------------------|
 *   | yes      | yes  | yes     | PURCHASE + SALE          |
 *   | yes      | no   | yes     | PURCHASE                 |
 *   | no       | yes  | yes     | OPENING (state) + SALE   |
 *   | no       | no   | yes     | OPENING (state)          |
 *   | no       | no   | no      | nothing (empty state)    |
 *
 * ── FINANCIAL SAFETY ────────────────────────────────────────────────────────
 * This module performs NO arithmetic. No `Number()`, no `parseFloat`, no
 * `+`/`-`, no `reduce` over money or quantity. It selects rows and nothing
 * else. The complete financial record stays `transactions`, and every total,
 * running balance, utilisation and closing figure must keep reading THAT.
 */

/** Types rendered as ordinary rows in the transaction table. */
export const DISPLAY_ROW_TYPES = ['PURCHASE', 'SALE'] as const;

/** The starting-state row. Never an ordinary transaction row. */
export const OPENING_ROW_TYPE = 'OPENING';

/**
 * The credit-direction display row type.
 *
 * Kept here purely so no component has to hard-code a transaction-type string
 * literal: within `DISPLAY_ROW_TYPES` a row is either a SALE (credit column)
 * or a PURCHASE (debit column).
 */
export const SALE_ROW_TYPE = 'SALE';

/**
 * Types whose presence suppresses the OPENING row.
 *
 * Strictly "PURCHASE" — COMMISSION_PURCHASE is deliberately excluded because
 * it is non-balance-affecting by approved semantics, so it cannot stand in for
 * the licence's opening position. Mirrors the backend tuple of the same name.
 */
export const PURCHASE_PRESENCE_TYPES = ['PURCHASE'] as const;

/** Minimum shape a row needs for the rule to apply to it. */
export interface LedgerDisplayRowLike {
    type?: string | null;
}

/** Result of applying the display rule. */
export interface LedgerDisplaySelection<TRow extends LedgerDisplayRowLike> {
    /** PURCHASE + SALE only, in payload order. Never contains OPENING. */
    rows: TRow[];
    /** The OPENING starting-state row, or null when a PURCHASE exists. */
    openingRow: TRow | null;
}

/**
 * Any ledger payload the rule can be read from.
 *
 * `display_transactions` / `opening_display` are the canonical presentation
 * fields served by `GET /api/license-ledger/{id}/ledger_detail/`. When they are
 * absent (older or cached responses) the rule is re-applied to `transactions`
 * by the compatibility shim below.
 */
export interface LedgerDisplayPayloadLike<TRow extends LedgerDisplayRowLike> {
    transactions?: readonly TRow[] | null;
    display_transactions?: readonly TRow[] | null;
    opening_display?: TRow | null;
}

function rowType(txn: LedgerDisplayRowLike | null | undefined): string {
    return typeof txn?.type === 'string' ? txn.type : '';
}

/** True for rows rendered as ordinary transactions (PURCHASE / SALE). */
export function isDisplayRow(txn: LedgerDisplayRowLike | null | undefined): boolean {
    return (DISPLAY_ROW_TYPES as readonly string[]).includes(rowType(txn));
}

/** True for SALE rows — the credit-direction half of `DISPLAY_ROW_TYPES`. */
export function isSaleRow(txn: LedgerDisplayRowLike | null | undefined): boolean {
    return rowType(txn) === SALE_ROW_TYPE;
}

/** True for the synthetic OPENING starting-state row. */
export function isOpeningRow(txn: LedgerDisplayRowLike | null | undefined): boolean {
    return rowType(txn) === OPENING_ROW_TYPE;
}

/** True for rows whose presence suppresses the OPENING row. */
function isPurchasePresenceRow(txn: LedgerDisplayRowLike | null | undefined): boolean {
    return (PURCHASE_PRESENCE_TYPES as readonly string[]).includes(rowType(txn));
}

/**
 * COMPATIBILITY SHIM — apply the rule directly to a transaction collection.
 *
 * Used for payloads that predate `display_transactions` / `opening_display`,
 * and by the export pipeline, whose rows have already been adapted into the
 * PDF/Excel shape. This is the ONLY place on the frontend that re-expresses
 * the rule; it is the single frontend expression of it, not a duplicate.
 */
export function selectDisplayRowsFromTransactions<TRow extends LedgerDisplayRowLike>(
    transactions: readonly TRow[] | null | undefined,
): LedgerDisplaySelection<TRow> {
    const all: readonly TRow[] = Array.isArray(transactions) ? transactions : [];

    // Order is preserved exactly as received — never re-sorted.
    const rows = all.filter(isDisplayRow);

    const openingRow = all.some(isPurchasePresenceRow)
        ? null
        : all.find(isOpeningRow) ?? null;

    return { rows, openingRow };
}

/**
 * Apply the display rule to a ledger payload.
 *
 * Reads the canonical `display_transactions` / `opening_display` fields
 * straight from the payload when present; otherwise falls back to the
 * compatibility shim over `transactions`.
 */
export function selectLedgerDisplayRows<TRow extends LedgerDisplayRowLike>(
    payload: LedgerDisplayPayloadLike<TRow> | null | undefined,
): LedgerDisplaySelection<TRow> {
    if (payload && Array.isArray(payload.display_transactions)) {
        return {
            rows: [...payload.display_transactions],
            openingRow: payload.opening_display ?? null,
        };
    }
    return selectDisplayRowsFromTransactions(payload?.transactions);
}

/**
 * Build a per-row predicate for a licence's transaction collection.
 *
 * For consumers (the PDF/Excel pipeline) that regroup and re-normalise the
 * transactions into fresh objects, so row identity from
 * `selectDisplayRowsFromTransactions` cannot be used. The OPENING decision is
 * still taken once, at licence level, exactly as the rule requires.
 */
export function createDisplayRowFilter<TRow extends LedgerDisplayRowLike>(
    transactions: readonly TRow[] | null | undefined,
): (txn: LedgerDisplayRowLike | null | undefined) => boolean {
    const { openingRow } = selectDisplayRowsFromTransactions(transactions);
    const showOpeningRow = openingRow !== null;
    return (txn) => isDisplayRow(txn) || (showOpeningRow && isOpeningRow(txn));
}
