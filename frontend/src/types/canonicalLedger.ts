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
  company_id: number | null;
  company_name: string | null;
  amount: string;
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

  opening_balance: string;
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
