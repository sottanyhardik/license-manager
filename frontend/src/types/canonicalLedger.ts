/**
 * Canonical Ledger API Types — Phase 4C/4D
 *
 * These types represent the single source of truth for all Ledger financial data.
 *
 * IMPORTANT:
 * - All financial values are STRINGS (Decimal representation)
 * - Do NOT perform arithmetic on these values in React
 * - Do NOT recalculate balances or utilizations
 * - Use only for display and presentation formatting
 *
 * The API (CanonicalLedgerService) is the authoritative source.
 */

/**
 * A single transaction in the canonical ledger dataset.
 *
 * `license_running_balance` = the balance at this point (authoritative)
 * `affects_balance` = whether this transaction is included in license_running_balance
 * `company_utilization_after` = that company's balance after this transaction (if applicable)
 */
export interface CanonicalTransaction {
  date: string;
  id: number;
  type: string;
  /**
   * OUR side of the trade — the company the ledger table GROUPS BY.
   *
   * NOT the party we traded with. Rendering this in the "Particulars" column
   * just echoes the group header; use `party_name` there.
   */
  company_id: number | null;
  company_name: string | null;
  /**
   * The COUNTERPARTY — the company shown in "Particulars": the supplier a
   * PURCHASE was bought from, the buyer a SALE went to.
   *
   * `null` when the relation is absent (the trade's company FK is nullable and
   * `SET_NULL`, so a deleted company really does leave a NULL party on a
   * historical trade). Render 'N/A' — never substitute `company_name` or the
   * licence holder, which would state that we traded with ourselves.
   *
   * Optional because older/cached responses predate the field.
   */
  party_id?: number | null;
  party_name?: string | null;
  /**
   * The LICENSE value this trade released/consumed — CIF FC (**USD**) for DFIA.
   * Rendered in the Debit column for PURCHASE, the Credit column for SALE.
   */
  amount: string;
  /**
   * The actual INVOICE value, always in **INR** (Σ line `amount_inr`).
   *
   * ⚠ A DIFFERENT QUANTITY IN A DIFFERENT CURRENCY FROM `amount` ⚠
   * A licence can be traded at any margin over the CIF it releases, so these
   * two are unrelated numbers. Never substitute one for the other, never sum
   * them together, never assume they are equal.
   *
   * `null` on the OPENING row — a carried-forward state has no invoice.
   */
  bill_amount?: string | null;
  /**
   * Billed licence item names — deduped, first-seen order. `[]` for incentive
   * licences (no item link exists in their data model) and for the OPENING row.
   *
   * A list, not a joined string: one trade is ONE ledger row however many items
   * it bills. Never expand a multi-item trade into multiple rows — that would
   * double-count it in the debit/credit columns.
   */
  item_names?: string[];
  is_commission: boolean;
  affects_balance: boolean;
  license_running_balance: string;
  company_utilization_after: string | null;
  display_status: string;
  /**
   * Comma-space joined SION norm classes for the licence items billed on this
   * trade, e.g. "E1, E5". DFIA-only — always `''` for incentive licences, for
   * DFIA trades whose items carry no norm, and for the synthetic OPENING row.
   *
   * NOTE: this is a presentation-layer derivation, not a ledger fact. There is
   * no per-transaction norm in the data model; the norm hangs off the item name.
   */
  sion_norms?: string | null;
}

/**
 * Per-company utilization breakdown.
 *
 * This is the company's portion of the license (derived by CanonicalLedgerService).
 */
export interface CompanyUtilization {
  company_id: number;
  company_name: string | null;
  utilization_balance: string;
}

/**
 * Aggregate transaction totals.
 */
export interface LedgerTotals {
  total_purchases: string;
  total_sales: string;
  total_commission: string;
}

/**
 * Backend-decided Profit / Loss state.
 *
 * The UI switches on THIS — never on the sign of `total_profit_loss`. That keeps
 * the web screen and (later) PDF/Excel agreeing, and makes exact zero
 * (`BREAK_EVEN` → "break-even") a real financial statement rather than
 * something each client re-derives.
 *
 * - PROFIT: positive balance, sell price > buy price
 * - LOSS: negative balance, sell price < buy price
 * - BREAK_EVEN: exactly zero profit/loss
 * - UNAVAILABLE: profit cannot be calculated (e.g., incentive licence)
 */
export type ProfitState = 'PROFIT' | 'LOSS' | 'BREAK_EVEN' | 'UNAVAILABLE';

/**
 * The on-screen summary block — every summary figure the ledger page displays,
 * computed once by `CanonicalLedgerService._build_summary`.
 *
 * DEBIT / CREDIT — ONE MEANING
 *   `total_credit` = Σ of the table's **Credit** column = PURCHASE rows
 *                    (+ the OPENING row when it is shown)
 *   `total_debit`  = Σ of the table's **Debit** column  = SALE rows
 * The ledger is the licence's own account: acquiring licence value credits it,
 * consuming licence value debits it. This agrees with each type's
 * `balance_direction`, so the two names cannot drift apart.
 *
 * ⚠ TWO CURRENCIES, NEVER MIXED ⚠
 *   `total_debit` / `total_credit` / `opening_balance` / `current_balance` /
 *   `total_profit_loss`                     → `balance_currency` (USD for DFIA)
 *   `total_debit_bill` / `total_credit_bill` → `bill_currency` (always INR)
 * Never add or compare figures across these two groups.
 *
 * THE IDENTITY the backend guarantees — unconditional, no correction term:
 *     total_credit − total_debit === current_balance === total_profit_loss
 *
 * `opening_balance` is licence metadata and is deliberately NOT part of it:
 * when a PURCHASE exists, the opening and that purchase are the same
 * acquisition, so adding it would double-count. The client renders these values;
 * it never performs the subtraction.
 */
export interface LedgerSummary {
  /** Σ of the displayed Debit column = sales. */
  total_debit: string;
  /** Σ of the displayed Credit column = purchases (+ opening iff `opening_in_credit`). */
  total_credit: string;
  /** Σ of the displayed Debit Bill column, in `bill_currency`. */
  total_debit_bill: string;
  /** Σ of the displayed Credit Bill column, in `bill_currency`. */
  total_credit_bill: string;
  /** Always 'INR' — bills are invoiced in rupees regardless of licence type. */
  bill_currency: string;
  /** The licence's face value. Metadata — NOT part of the identity above. */
  opening_balance: string;
  /**
   * True when the OPENING row is on screen (no PURCHASE exists) and is therefore
   * ALREADY counted inside `total_credit`. Published so no client re-derives the
   * display rule.
   */
  opening_in_credit: boolean;
  /**
   * THE canonical balance: `total_credit − total_debit`. Display as given.
   * Never recompute it, and never substitute `license_running_balance` — that
   * field double-counts the acquisition of a purchased licence.
   */
  current_balance: string;
  balance_currency: 'USD' | 'INR';
  /**
   * The SAME number as `current_balance` — one backend calculation surfaced
   * under two labels, not two figures that happen to agree. Signed: negative
   * means a loss (the label carries the direction, so the card shows the
   * magnitude). Always present.
   *
   * NOTE: this is the licence's unutilised position, NOT the realised INR
   * trading margin shown by the Purchase & Profit report. Different question,
   * different currency — do not expect the two screens to match.
   */
  total_profit_loss: string;
  /** Equals `balance_currency`. Profit is in licence value, never in bill INR. */
  profit_currency: string;
  profit_state: ProfitState;
}

/**
 * Complete canonical ledger dataset for a license.
 *
 * This is the authoritative source of truth for all Ledger financial data.
 * The UI consumes this exactly as provided by the API.
 * No independent calculations, no transformations.
 */
export interface CanonicalLedgerResponse {
  license_id: number;
  license_type: string;
  license_number: string;
  license_date: string;
  expiry_date: string;
  exporter_id: number | null;
  exporter_name: string | null;
  port_id: number | null;
  port_name: string | null;
  /**
   * The licence's canonical acquisition date: MIN(qualifying purchase invoice
   * date). This is the field the ledger list's Purchase Date Range filters on.
   *
   * `null` when the licence has no qualifying purchase, and for incentive
   * licences (the canonical definition does not reach them).
   */
  first_purchase_date?: string | null;

  opening_balance: string;
  /**
   * Opening + Σpurchases − Σsales. ⚠ For a PURCHASED licence this
   * DOUBLE-COUNTS the acquisition (the opening balance and the purchase trade
   * are the same event), so it is NOT the figure to show as "Current Balance" —
   * use `summary.current_balance`. Retained for consumers that specifically
   * want the raw running figure.
   */
  license_running_balance: string;
  closing_balance: string;

  /**
   * The COMPLETE financial record. Every running balance, total and
   * balance-by-id map is derived from this — never filter it for arithmetic.
   */
  transactions: CanonicalTransaction[];

  /**
   * PRESENTATION ONLY — the rows the ledger table should render.
   *
   * PURCHASE and SALE only, chronological order preserved, NEVER contains
   * OPENING. Produced server-side by `select_display_rows()`; consume it via
   * `selectLedgerDisplayRows()` in `@/utils/ledgerDisplayRows`, not directly.
   *
   * Optional because older/cached responses predate the field.
   */
  display_transactions?: CanonicalTransaction[];

  /**
   * PRESENTATION ONLY — the OPENING row, to be rendered as the starting state
   * rather than as an ordinary transaction.
   *
   * Non-null only when no PURCHASE exists (and an opening balance exists).
   */
  opening_display?: CanonicalTransaction | null;

  company_utilizations: Record<string, CompanyUtilization>;
  totals: LedgerTotals;

  /**
   * The on-screen reconciliation block + canonical Profit / Loss.
   *
   * Optional ONLY because older/cached responses predate the field — the live
   * API always sends it. Consumers must degrade gracefully (hide the summary
   * cards) rather than rendering fabricated zeros.
   */
  summary?: LedgerSummary;

  // Deprecated fields (Phase 4C backward compatibility only)
  // DO NOT USE in Phase 4D+
  available_balance?: string;
  db_balance?: string;
}

/**
 * Validated canonical ledger response.
 *
 * Same as CanonicalLedgerResponse, but guarantees:
 * - All required fields are present
 * - All values are properly typed and non-null where required
 */
export interface ValidatedCanonicalLedger extends CanonicalLedgerResponse {
  license_number: string;
  license_type: string;
  transactions: CanonicalTransaction[];
}
